import asyncio
import copy
import http.server
import itertools
import json
import os
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_fansly_api import DM_CREATOR, DM_CREATOR_ID, FakeSession, both_routes, envelope, fansly, load  # noqa: F401

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.posts.post as post
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings
from ofscraper.commands import stash_sync
from ofscraper.commands.stash_sync import StashError, map_path, read_model, sync
from ofscraper.db.operations_.media import batch_mediainsert, mark_media_as_downloaded, mediaCreate
from ofscraper.db.operations_.messages import messagesCreate
from ofscraper.db.operations_.others import schemaCreate, siteInsert
from ofscraper.db.operations_.posts import postCreate
from ofscraper.db.operations_.profile import profilesCreate


def like(value, pattern):
    """SQLite LIKE without ESCAPE, as Stash uses it: ASCII case ignored, _ is one character, % any."""
    rx = "".join("." if c == "_" else ".*" if c == "%" else re.escape(c) for c in pattern)
    return re.fullmatch(rx, value or "", flags=re.I | re.S) is not None


class FakeStash:
    """Just enough of Stash's GraphQL API for stash_sync."""

    def __init__(self, scenes=(), images=()):
        ids = itertools.count(100)
        self.next_id = lambda: str(next(ids))
        self.items = {"scene": {}, "image": {}}
        for kind, paths in (("scene", scenes), ("image", images)):
            for path in paths:
                self.add(kind, path)
        self.entities = {"studio": {}, "tag": {}, "performer": {}}
        self.aliases = {"studio": {}, "tag": {}, "performer": {}}  # id -> aliases
        self.disambiguation = {}  # performer id -> disambiguation
        self.galleries = {}
        self.created = []
        self.updates = []
        self.mutations = []  # every mutation sent, refused or not

    def add(self, kind, path, **fields):
        item = {"id": self.next_id(), "title": "", "details": "", "date": None, "code": "", "urls": [],
                "organized": False, "studio": None, "performers": [], "tags": [], "galleries": [],
                "path": path, **fields}
        self.items[kind][item["id"]] = item
        return item

    @staticmethod
    def _apply(item, change):
        for key, field in (("studio_id", None), ("performer_ids", "performers"), ("tag_ids", "tags"),
                           ("gallery_ids", "galleries")):
            if key in change:
                value = change.pop(key)
                if field is None:
                    item["studio"] = {"id": value}
                else:
                    item[field] = [{"id": i} for i in value]
        item.update(change)

    def call(self, query, variables=None):
        variables = variables or {}
        if query.lstrip().startswith("mutation"):
            self.mutations.append(query)
        if "findGalleries" in query:
            found = [dict(g) for g in self.galleries.values() if g["code"] == variables["code"]]
            return {"findGalleries": {"galleries": found}}
        if "galleryCreate" in query:
            gallery = {"id": self.next_id(), "title": "", "details": "", "date": None, "code": "", "urls": [],
                       "organized": False, "studio": None, "performers": [], "tags": []}
            change = dict(variables["input"])
            self.created.append(("gallery", dict(change)))
            self._apply(gallery, change)
            self.galleries[gallery["id"]] = gallery
            return {"galleryCreate": {"id": gallery["id"]}}
        if "galleryUpdate" in query:
            change = dict(variables["input"])
            self.updates.append(("gallery", dict(change)))
            self._apply(self.galleries[change.pop("id")], change)
            return {"galleryUpdate": {"id": variables["input"]["id"]}}
        for kind, find, key in (("scene", "findScenes", "scenes"), ("image", "findImages", "images")):
            if find in query:
                found = [dict(i, files=[{"path": i["path"]}], visual_files=[{"path": i["path"]}])
                         for i in self.items[kind].values() if i["path"] == variables["path"]]
                return {find: {key: found}}
            if f"{kind}Update" in query:
                change = dict(variables["input"])
                self.updates.append((kind, change))
                item = self.items[kind][change.pop("id")]
                self._apply(item, dict(change))
                return {f"{kind}Update": {"id": item["id"]}}
        for entity, plural in (("studio", "Studios"), ("tag", "Tags"), ("performer", "Performers")):
            alias_field = "alias_list" if entity == "performer" else "aliases"
            if f"find{plural}" in query:
                # like Stash v0.31.1, EQUALS on name or aliases is SQL LIKE:
                # it ignores case, and "_" and "%" are wildcards
                want = variables["name"]
                by_alias = "aliases: {" in query
                found = [
                    {"id": i, "name": n, alias_field: self.aliases[entity].get(i, [])}
                    for n, i in self.entities[entity].items()
                    if any(like(v, want) for v in (self.aliases[entity].get(i, []) if by_alias else [n]))
                ]
                return {f"find{plural}": {plural.lower(): found}}
            if f"{entity}Create" in query:
                new_input = variables["input"]
                name = new_input["name"]
                for n, i in self.entities[entity].items():
                    aliases = self.aliases[entity].get(i, [])
                    if entity == "tag":  # name or alias, ignoring case
                        clash = name.lower() in [n.lower()] + [a.lower() for a in aliases]
                    elif entity == "studio":  # name LIKE, then aliases LIKE
                        clash = like(n, name) or any(like(a, name) for a in aliases)
                    else:  # name LIKE, with the same disambiguation (or none)
                        clash = like(n, name) and self.disambiguation.get(i) == new_input.get("disambiguation")
                    if clash:
                        raise StashError(f"{entity} with name '{name}' already exists")
                new = self.next_id()
                self.entities[entity][name] = new
                self.disambiguation[new] = new_input.get("disambiguation")
                self.created.append((entity, new_input))
                return {f"{entity}Create": {"id": new}}
        raise AssertionError(f"unexpected query: {query}")

    def entity(self, kind, name, aliases=()):
        """An entity the user already has in Stash."""
        new = self.next_id()
        self.entities[kind][name] = new
        self.aliases[kind][new] = list(aliases)
        return new


@pytest.fixture
def library(tmp_path):
    db = tmp_path / ".data" / "123" / "user_data.db"
    db.parent.mkdir(parents=True)
    media_dir = tmp_path / "creator"
    with closing(sqlite3.connect(db)) as conn, conn:
        for create in (mediaCreate, postCreate, messagesCreate, profilesCreate):
            conn.execute(create)
        conn.execute("INSERT INTO profiles (user_id, username) VALUES (123, 'creator')")
        conn.execute("INSERT INTO posts (post_id, text, model_id) VALUES (1001, 'First line &amp; more<br />second line', 123)")
        conn.execute("INSERT INTO messages (post_id, text, model_id) VALUES (2002, '<p>hi there</p>', 123)")
        rows = [
            (1, 1001, "post.mp4", "Timeline", "Videos", 1),
            (2, 1001, "post.jpg", "Timeline", "Images", 1),
            (3, 2002, "msg.jpg", "Messages", "Images", 1),
            (3, 2003, "msg.jpg", "Paid", "Images", 1),  # same file, recorded again as a purchase
            (4, "0123abcdef", "avatar.jpg", "Profile", "Images", 1),
            (5, 1001, "audio.mp3", "Timeline", "Audios", 1),
            (6, 1001, "skipped.jpg", "Timeline", "Images", 0),
        ]
        for media_id, post_id, name, api_type, media_type, downloaded in rows:
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, api_type, media_type, downloaded, "
                "posted_at, created_at, model_id) VALUES (?,?,?,?,?,?,?,?,?,123)",
                (media_id, post_id, str(media_dir), name, api_type, media_type, downloaded,
                 "2025-02-27T23:12:05+00:00", "2025-02-27T23:12:05+00:00"),
            )
    return db, media_dir


def test_read_model_describes_each_file(library):
    db, media_dir = library
    username, files = read_model(db)
    assert username == "creator"
    by_name = {f["path"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1]: f for f in files}
    assert set(by_name) == {"post.mp4", "post.jpg", "msg.jpg", "avatar.jpg", "audio.mp3"}

    post = by_name["post.mp4"]["meta"]
    assert post == {
        "code": "1001",
        "details": "First line & more\nsecond line",
        "title": "First line & more",
        "date": "2025-02-27",
        "url": "https://onlyfans.com/1001/creator",
    }
    msg = by_name["msg.jpg"]
    assert msg["api_types"] == {"Messages", "Paid"}
    assert msg["meta"]["details"] == "hi there"
    assert "url" not in msg["meta"]  # messages have no public page
    assert by_name["avatar.jpg"]["meta"]["code"] is None


def test_preview_changes_nothing_and_apply_fills_everything(library):
    db, media_dir = library
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")], images=[str(media_dir / "post.jpg"), str(media_dir / "msg.jpg")])

    preview = sync([db], stash)
    assert stash.updates == [] and stash.created == []
    assert preview["totals"] == {"files": 5, "to_update": 3, "not_in_stash": 1, "unsupported_type": 1}

    report = sync([db], stash, apply=True)
    assert report["totals"]["updated"] == 3
    scene = next(iter(stash.items["scene"].values()))
    performer = stash.entities["performer"]["creator"]
    assert scene["title"] == "First line & more"
    assert scene["code"] == "1001" and scene["date"] == "2025-02-27"
    assert scene["urls"] == ["https://onlyfans.com/1001/creator"]
    assert scene["studio"] == {"id": stash.entities["studio"]["OnlyFans"]}
    assert scene["performers"] == [{"id": performer}]
    assert scene["tags"] == [{"id": stash.entities["tag"]["OnlyFans Timeline"]}]
    msg = next(i for i in stash.items["image"].values() if i["path"].endswith("msg.jpg"))
    assert {t["id"] for t in msg["tags"]} == {stash.entities["tag"]["OnlyFans Messages"], stash.entities["tag"]["OnlyFans Paid"]}
    assert ("performer", {"name": "creator", "urls": ["https://onlyfans.com/creator"]}) in stash.created

    again = sync([db], stash, apply=True)
    assert again["totals"]["up_to_date"] == 3 and "updated" not in again["totals"]


def test_existing_stash_values_are_kept(library):
    db, media_dir = library
    stash = FakeStash()
    stash.entities["performer"]["someone else"] = "7"
    stash.entities["tag"]["mine"] = "8"
    item = stash.add("scene", str(media_dir / "post.mp4"), title="My title", date="2020-01-01",
                     urls=["https://example.com"], performers=[{"id": "7"}], tags=[{"id": "8"}])

    sync([db], stash, apply=True)
    assert item["title"] == "My title" and item["date"] == "2020-01-01"
    assert item["details"] == "First line & more\nsecond line"  # was empty, so filled
    assert item["urls"] == ["https://example.com", "https://onlyfans.com/1001/creator"]
    assert [p["id"] for p in item["performers"]] == ["7", stash.entities["performer"]["creator"]]
    assert [t["id"] for t in item["tags"]][0] == "8"


def test_organized_only_when_asked(library):
    db, media_dir = library
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")])
    sync([db], stash, apply=True)
    item = next(iter(stash.items["scene"].values()))
    assert not item["organized"]
    sync([db], stash, apply=True, organized=True)
    assert item["organized"] is True


def test_nothing_matched_creates_nothing_and_hints(library):
    # e.g. Stash in Docker sees the files under /data and --path-map was forgotten
    db, _ = library
    stash = FakeStash(scenes=["/data/creator/post.mp4"])
    report = sync([db], stash, apply=True)
    assert stash.created == [] and stash.updates == []
    model = report["models"][0]
    assert model["not_in_stash"] == 4 and model["performer_exists"] is False
    assert "--path-map" in model["hint"]


def test_path_map_finds_files_stash_sees_elsewhere(library):
    db, media_dir = library
    stash = FakeStash(scenes=["/data/creator/post.mp4"])
    report = sync([db], stash, apply=True, mappings=[(str(media_dir.parent), "/data")])
    assert report["totals"]["updated"] == 1


def test_map_path():
    assert map_path(r"C:\dl\a\b.jpg", [(r"C:\dl", "/data")]) == "/data/a/b.jpg"
    assert map_path(r"C:\dl2\b.jpg", [(r"C:\dl", "/data")]) == r"C:\dl2\b.jpg"
    assert map_path("/srv/dl/b.jpg", [("/srv/dl", "/media")]) == "/media/b.jpg"


def test_map_path_accepts_either_separator(monkeypatch):
    # As on Linux CI: a Windows path from the database still maps
    monkeypatch.setattr(stash_sync.os, "sep", "/")
    assert map_path(r"C:\dl\a\b.jpg", [(r"C:\dl", "/data")]) == "/data/a/b.jpg"
    assert map_path("C:\\dl/a/b.jpg", [(r"C:\dl", "/data")]) == "/data/a/b.jpg"
    assert map_path(r"C:\dl", [("C:\\dl\\", "/data")]) == "/data"
    assert map_path("/srv/dl", [("/srv/dl", "/media")]) == "/media"
    assert map_path("/srv/dlx/b.jpg", [("/srv/dl", "/media")]) == "/srv/dlx/b.jpg"


@pytest.mark.parametrize("sep", ["\\", "/"])
def test_map_path_windows_prefix_ignores_case_and_slashes(monkeypatch, sep):
    monkeypatch.setattr(stash_sync.os, "sep", sep)
    stored = r"C:\dl\Sub\b.jpg"
    for local in (r"c:\dl", "C:/dl", "c:/DL/", r"C:\dl"):
        assert map_path(stored, [(local, "/data")]) == "/data/Sub/b.jpg", local
    assert map_path("C:/dl/Sub/b.jpg", [(r"C:\DL", "/data")]) == "/data/Sub/b.jpg"
    assert map_path(r"C:\dl", [("c:/dl", "/data")]) == "/data"
    assert map_path(r"\\NAS\Share\dl\a.jpg", [(r"\\nas\share", "/data")]) == "/data/dl/a.jpg"
    assert map_path(r"\\nas\share\dl\a.jpg", [("//nas/share/", "/data")]) == "/data/dl/a.jpg"
    # partial folder names still don't match
    assert map_path(r"C:\dl2\x.jpg", [("c:/dl", "/data")]) == r"C:\dl2\x.jpg"
    assert map_path(r"\\nas\share2\x.jpg", [(r"\\NAS\share", "/data")]) == r"\\nas\share2\x.jpg"


@pytest.mark.parametrize("sep", ["\\", "/"])
def test_map_path_posix_prefix_unchanged(monkeypatch, sep):
    monkeypatch.setattr(stash_sync.os, "sep", sep)
    assert map_path("/srv/DL/b.jpg", [("/srv/dl", "/media")]) == "/srv/DL/b.jpg"
    assert map_path("/srv/dlx/b.jpg", [("/srv/dl", "/media")]) == "/srv/dlx/b.jpg"
    assert map_path("/srv/dl/b.jpg", [("/srv/dl/", "/media")]) == "/media/b.jpg"
    assert map_path("/srv/dl/b.jpg", [("/", "/media")]) == "/media/srv/dl/b.jpg"


# --- Fansly -----------------------------------------------------------------

FRIEND = "samplefriend"
MENTION_POST = 100000000000000004


FIRST_POST = 100000000000000001
BOUGHT_TOO = 100000000000000149  # an item of a message, also bought on its own
PURCHASE = 100000000000000900  # a made-up item that was only bought
PURCHASE_MEDIA = 100000000000000901
MESSAGE, GROUP = 100000000000000142, 100000000000000143  # a message in the fixtures, and its conversation
OTHER_MESSAGE = 100000000000000147  # another message in the same conversation
MESSAGE_URL = f"https://fansly.com/messages/{GROUP}"  # a message's page is its conversation's
OLD_MESSAGE_URL = f"https://fansly.com/messages/{GROUP}/{MESSAGE}"  # what #356 wrote; not a Fansly page


def fansly_routes(edits=None, purchases=False):
    """The Fansly fixtures, with one post mentioning another creator.

    edits replaces captions by post or message ID; purchases answers the
    purchases call with one order.
    """
    edits = {MENTION_POST: f"{{}} with @{FRIEND}", **(edits or {})}

    def route(path, query):
        if purchases and path.startswith("account/media/orders"):
            account_media = load("messages.json")["response"]["accountMedia"]
            only = copy.deepcopy(next(m for m in account_media if int(m["id"]) == BOUGHT_TOO))
            only.update(id=str(PURCHASE), access=True)
            only.pop("preview", None)
            only.pop("previewId", None)
            only["media"]["id"] = str(PURCHASE_MEDIA)
            orders = [{"accountMediaId": str(i), "createdAt": 1777913614} for i in (BOUGHT_TOO, PURCHASE)]
            return envelope({"accountMediaOrders": orders, "accountMedia": account_media + [only]})
        data = both_routes(path, query)
        response = data.get("response")
        items = (response.get("posts") or []) + (response.get("messages") or []) if isinstance(response, dict) else []
        for item in items:
            if int(item["id"]) in edits:
                item["content"] = edits[int(item["id"])].format(item["content"])
        return data

    return route


@pytest.fixture
def fansly_library(fansly, monkeypatch, tmp_path):
    """A Fansly creator's database written by the real Fansly scrape and download code.

    make_fansly builds a variant, with caption edits or a purchase.
    """
    return build_fansly(monkeypatch, tmp_path)


@pytest.fixture
def make_fansly(fansly, monkeypatch, tmp_path):
    return lambda **kwargs: build_fansly(monkeypatch, tmp_path, **kwargs)


def build_fansly(monkeypatch, tmp_path, edits=None, purchases=False):
    db = tmp_path / ".data" / "Fansly" / str(DM_CREATOR_ID) / "user_data.db"
    db.parent.mkdir(parents=True)
    monkeypatch.setattr(placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db)
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    media_dir = tmp_path / "fansly"

    async def scrape():
        c = FakeSession(fansly_routes(edits, purchases))
        await operations.table_init_create(model_id=DM_CREATOR_ID, username=DM_CREATOR)
        timeline, _ = await post.process_timeline_posts(DM_CREATOR_ID, DM_CREATOR, c)
        messages, _ = await post.process_messages(DM_CREATOR_ID, DM_CREATOR, c)
        found = timeline + messages
        if purchases:
            paid, _ = await post.process_paid_post(DM_CREATOR_ID, DM_CREATOR, c)
            found += paid
        media = [m for p in found for m in p.all_media]
        await batch_mediainsert(media, model_id=DM_CREATOR_ID, username=DM_CREATOR, downloaded=False)
        for m in media:
            ext = "mp4" if m.mediatype.lower() == "videos" else "jpg"
            await mark_media_as_downloaded(
                m, model_id=DM_CREATOR_ID, username=DM_CREATOR, filepath=media_dir / f"{m.id}.{ext}", downloaded=True
            )

    asyncio.run(scrape())
    with closing(sqlite3.connect(db)) as conn:
        rows = conn.execute("SELECT DISTINCT directory, filename, media_type FROM medias WHERE downloaded = 1").fetchall()
    files = [(os.path.join(d, f), stash_sync.KINDS[t]) for d, f, t in rows]
    return db, media_dir, files


@pytest.fixture
def stash_server():
    """FakeStash behind a local HTTP GraphQL endpoint."""
    stash = FakeStash()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            try:
                answer = {"data": stash.call(body["query"], body["variables"])}
            except StashError as e:
                answer = {"data": None, "errors": [{"message": str(e)}]}
            data = json.dumps(answer).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield stash, f"http://127.0.0.1:{server.server_port}/graphql"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def named(stash, item):
    """An item or gallery with its studio, performers, tags and galleries by name."""
    names = {i: n for found in stash.entities.values() for n, i in found.items()}
    return {
        "studio": names.get((item["studio"] or {}).get("id")),
        "performers": sorted(names[p["id"]] for p in item["performers"]),
        "tags": sorted(names[t["id"]] for t in item["tags"]),
        "galleries": sorted(stash.galleries[g["id"]]["code"] for g in item.get("galleries", [])),
        **{k: item[k] for k in ("title", "details", "date", "code", "urls", "organized")},
    }


def by_file(stash, name):
    return next(i for kind in stash.items.values() for i in kind.values() if Path(i["path"]).name == name)


def test_fansly_and_onlyfans_end_to_end(library, fansly_library, stash_server, tmp_path, capsys):
    of_db, of_dir = library
    _, _, fansly_files = fansly_library
    stash, url = stash_server
    for path, kind in fansly_files:
        stash.add(kind, path)
    of_files = (("post.mp4", "scene"), ("post.jpg", "image"), ("msg.jpg", "image"))
    for name, kind in of_files:
        stash.add(kind, str(of_dir / name))
    data = str(tmp_path / ".data")

    # preview creates nothing
    assert stash_sync.main([data, "--url", url]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert stash.created == [] and stash.updates == []
    assert preview["totals"]["galleries_to_create"] == 5

    assert stash_sync.main([data, "--url", url, "--apply"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["totals"]["updated"] == len(fansly_files) + 3
    assert report["totals"]["galleries_created"] == 5  # 3 posts, 2 messages
    assert report["totals"]["not_in_stash"] == 1  # the OnlyFans avatar, not added to Stash here

    created = [c for c in stash.created if c[0] in ("studio", "performer")]
    assert ("studio", {"name": "Fansly", "urls": ["https://fansly.com"]}) in created
    assert ("studio", {"name": "OnlyFans", "urls": ["https://onlyfans.com"]}) in created
    assert ("performer", {"name": DM_CREATOR, "urls": [f"https://fansly.com/{DM_CREATOR}"]}) in created
    assert ("performer", {"name": FRIEND, "urls": [f"https://fansly.com/{FRIEND}"]}) in created

    post_url = f"https://fansly.com/post/{MENTION_POST}"
    text = f"Sample text 2 #weekend #behindthescenes with @{FRIEND}"
    assert named(stash, by_file(stash, "100000000000000026.mp4")) == {
        "studio": "Fansly",
        "performers": sorted([DM_CREATOR, FRIEND]),
        "tags": ["Fansly Timeline", "behindthescenes", "weekend"],
        "galleries": [str(MENTION_POST)],
        "title": text,
        "details": text,
        "date": "2026-11-06",
        "code": "100000000000000026",
        "urls": [post_url],
        "organized": False,
    }
    # in two posts: the earlier one's details, and both galleries
    shared = named(stash, by_file(stash, "100000000000000019.mp4"))
    assert shared["urls"] == ["https://fansly.com/post/100000000000000001"]
    assert shared["code"] == "100000000000000019"
    assert shared["performers"] == [DM_CREATOR]
    assert shared["galleries"] == ["100000000000000001", str(MENTION_POST)]
    assert shared["tags"] == ["Fansly Timeline", "outfit", "studio"]
    assert "Fansly Preview" in named(stash, by_file(stash, "100000000000000051.jpg"))["tags"]
    message = named(stash, by_file(stash, "100000000000000229.jpg"))
    assert message["urls"] == [MESSAGE_URL]  # from the stored conversation id
    assert message["code"] == "100000000000000229"
    assert message["tags"] == ["Fansly Messages", "behindthescenes", "studio"]
    assert message["galleries"] == ["100000000000000142"]

    galleries = {g["code"]: named(stash, g) for g in stash.galleries.values()}
    assert galleries[str(MENTION_POST)] == {
        "studio": "Fansly",
        "performers": sorted([DM_CREATOR, FRIEND]),
        "tags": ["Fansly Timeline", "behindthescenes", "weekend"],
        "galleries": [],
        "title": text,
        "details": text,
        "date": "2026-11-06",
        "code": str(MENTION_POST),
        "urls": [post_url],
        "organized": False,
    }
    assert galleries["100000000000000142"]["urls"] == [MESSAGE_URL]
    assert galleries["100000000000000142"]["tags"] == ["Fansly Messages", "behindthescenes", "studio"]

    # OnlyFans items come out exactly as from a run over the OnlyFans database alone
    alone = FakeStash()
    for name, kind in of_files:
        alone.add(kind, str(of_dir / name))
    sync([of_db], alone, apply=True)
    for name, _ in of_files:
        assert named(stash, by_file(stash, name)) == named(alone, by_file(alone, name))

    # a second run changes nothing
    created, updates = len(stash.created), len(stash.updates)
    assert stash_sync.main([data, "--url", url, "--apply"]) == 0
    again = json.loads(capsys.readouterr().out)["totals"]
    assert again["up_to_date"] == len(fansly_files) + 3
    assert again["galleries_up_to_date"] == 5
    assert "updated" not in again and "galleries_created" not in again
    assert (len(stash.created), len(stash.updates)) == (created, updates)


def test_fansly_gallery_is_found_in_any_studio(fansly_library, tmp_path):
    _, _, files = fansly_library
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    # an OnlyFans gallery the user made, with the same code
    stash.galleries["of"] = {"id": "of", "title": "mine", "details": "", "date": None, "code": str(MENTION_POST),
                             "urls": [f"https://onlyfans.com/{MENTION_POST}/someone"], "organized": False,
                             "studio": None, "performers": [], "tags": []}
    sync([tmp_path / ".data"], stash, apply=True)
    assert len(stash.galleries) == 6
    assert stash.galleries["of"]["title"] == "mine" and stash.galleries["of"]["performers"] == []

    # the user moves every Fansly gallery to their own studio, then runs with another --studio
    own = stash.entity("studio", "Creator's studio")
    for key, gallery in stash.galleries.items():
        if key != "of":
            gallery["studio"] = {"id": own}
    report = sync([tmp_path / ".data"], stash, apply=True, studio="Other")
    assert len(stash.galleries) == 6
    assert "galleries_created" not in report["totals"]
    assert all(g["studio"] == {"id": own} for k, g in stash.galleries.items() if k != "of")


def test_one_studio_for_both_sites_gets_no_site_link(library, fansly_library, tmp_path):
    _, of_dir = library
    _, _, files = fansly_library
    stash = FakeStash(scenes=[str(of_dir / "post.mp4")])
    for path, kind in files:
        stash.add(kind, path)
    sync([tmp_path / ".data"], stash, apply=True, studio="Everything")
    assert [v for kind, v in stash.created if kind == "studio"] == [{"name": "Everything"}]


def test_one_site_with_studio_keeps_its_link(library):
    db, media_dir = library
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")])
    sync([db], stash, apply=True, studio="Mine")
    assert [v for kind, v in stash.created if kind == "studio"] == [{"name": "Mine", "urls": ["https://onlyfans.com"]}]


@pytest.mark.parametrize(
    "urls, reused",
    [
        ([], True),
        ([f"https://fansly.com/post/{MENTION_POST}"], True),
        (["https://FANSLY.com/someone"], True),
        (["https://example.com/a"], False),
        (["https://notfansly.com/a"], False),
        ([f"https://OnlyFans.com/{MENTION_POST}/someone"], False),
    ],
)
def test_gallery_with_the_code_is_reused_only_if_unlinked_or_fansly(fansly_library, tmp_path, urls, reused):
    _, _, files = fansly_library
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    stash.galleries["mine"] = {"id": "mine", "title": "mine", "details": "", "date": None, "code": str(MENTION_POST),
                               "urls": list(urls), "organized": False, "studio": None, "performers": [], "tags": []}
    sync([tmp_path / ".data"], stash, apply=True)
    item = by_file(stash, "100000000000000026.mp4")
    assert ({"id": "mine"} in item["galleries"]) is reused
    assert len(stash.galleries) == (5 if reused else 6)
    if not reused:
        assert stash.galleries["mine"]["urls"] == urls and stash.galleries["mine"]["performers"] == []


def test_fansly_existing_values_are_kept(fansly_library, tmp_path):
    _, _, fansly_files = fansly_library
    stash = FakeStash()
    for path, kind in fansly_files:
        stash.add(kind, path)
    item = by_file(stash, "100000000000000026.mp4")
    item.update(title="mine", code="custom")
    sync([tmp_path / ".data"], stash, apply=True)
    assert (item["title"], item["code"]) == ("mine", "custom")
    # the empty ones are still filled
    assert named(stash, item)["studio"] == "Fansly"
    assert item["urls"] == [f"https://fansly.com/post/{MENTION_POST}"]


def test_names_in_another_case_or_an_alias_are_reused(make_fansly, tmp_path):
    # one post mentions @Pal, another @pal; the user has "Weekend", a tag
    # "Studio Shots" with the alias "studio", and the creator in capitals
    _, _, files = make_fansly(edits={MENTION_POST: "{} @Pal", FIRST_POST: "{} @pal"})
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    weekend = stash.entity("tag", "Weekend")
    studio_tag = stash.entity("tag", "Studio Shots", aliases=["studio"])
    creator = stash.entity("performer", DM_CREATOR.upper())

    report = sync([tmp_path / ".data"], stash, apply=True)

    assert report["totals"]["updated"] == len(files)
    created = {(kind, value["name"].lower()) for kind, value in stash.created if kind != "gallery"}
    assert not created & {("tag", "weekend"), ("tag", "studio"), ("performer", DM_CREATOR)}
    assert [name for kind, name in created if name == "pal"] == ["pal"]  # created once
    item = by_file(stash, "100000000000000026.mp4")
    assert {"id": weekend} in item["tags"] and {"id": creator} in item["performers"]
    assert {"id": studio_tag} in by_file(stash, "100000000000000019.mp4")["tags"]


def test_fansly_purchase_gets_no_gallery_or_post_link(make_fansly, tmp_path):
    db, _, files = make_fansly(purchases=True)
    with closing(sqlite3.connect(db)) as conn:
        bought = {
            name for (name,) in conn.execute(
                "SELECT filename FROM medias WHERE downloaded = 1 GROUP BY filename "
                "HAVING SUM(post_id != ?) = 0", (PURCHASE,))
        }
        # the purchase is stored like a post, under the item's own ID
        assert conn.execute("SELECT COUNT(*) FROM posts WHERE post_id = ?", (PURCHASE,)).fetchone()[0] == 1
    assert bought, "the fixture should have a file that was only bought"
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)

    sync([tmp_path / ".data"], stash, apply=True)

    codes = {g["code"] for g in stash.galleries.values()}
    assert not codes & {str(PURCHASE), str(BOUGHT_TOO)}
    assert len(stash.galleries) == 5
    assert {f"{PURCHASE_MEDIA}.jpg", f"{PURCHASE_MEDIA}.mp4"} & bought
    for name in bought:
        item = named(stash, by_file(stash, name))
        assert item["urls"] == [] and item["galleries"] == []
        assert "Fansly Paid" in item["tags"] and item["studio"] == "Fansly"
    # bought, and also in a message: only the message's gallery
    also = named(stash, by_file(stash, "100000000000000150.mp4"))
    assert also["galleries"] == ["100000000000000147"]
    assert "Fansly Paid" in also["tags"]


OF_ID, OF_USER = 12345, "ofcreator"


def of_item(item_id, media_id, kind="photo", **fields):
    return {"id": item_id, "text": f"caption {item_id}", "price": 5, "isOpened": True,
            "postedAt": "2024-05-01T10:00:00+00:00", "createdAt": "2024-05-01T10:00:00+00:00",
            "media": [{"id": media_id, "type": kind, "canView": True, "createdAt": "2024-05-01T10:00:00+00:00",
                       "files": {"full": {"url": f"https://cdn.example/{media_id}"}}}], **fields}


@pytest.fixture
def onlyfans_paid(monkeypatch, tmp_path):
    """An OnlyFans database from the real write path: a timeline post, a
    message also bought, and a post seen only as a purchase."""
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    monkeypatch.setattr(settings, "get_settings", lambda: Stub(site="onlyfans", after=None, post_id=None))
    db = tmp_path / ".data" / str(OF_ID) / "user_data.db"
    db.parent.mkdir(parents=True)
    monkeypatch.setattr(placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db)
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    media_dir = tmp_path / "of"
    message = of_item(3001, 4001, responseType="message", fromUser={"id": OF_ID})

    async def write():
        await operations.table_init_create(model_id=OF_ID, username=OF_USER)
        timeline = posts_.Post(of_item(1001, 2001, responseType="post"), OF_ID, OF_USER, "Timeline")
        messages = posts_.Post(message, OF_ID, OF_USER)
        bought = [posts_.Post(copy.deepcopy(message), OF_ID, OF_USER, responsetype="Paid"),
                  posts_.Post(of_item(5001, 6001, responseType="post"), OF_ID, OF_USER, responsetype="Paid")]
        await operations.make_post_table_changes([timeline, *bought], model_id=OF_ID, username=OF_USER)
        await operations.make_messages_table_changes([messages], model_id=OF_ID, username=OF_USER)
        media = [m for p in (timeline, messages, *bought) for m in p.all_media]
        await batch_mediainsert(media, model_id=OF_ID, username=OF_USER, downloaded=False)
        for m in media:
            await mark_media_as_downloaded(m, model_id=OF_ID, username=OF_USER,
                                           filepath=media_dir / f"{m.id}.jpg", downloaded=True)

    asyncio.run(write())
    return db, media_dir


def test_onlyfans_bought_message_gets_no_post_link(onlyfans_paid):
    db, media_dir = onlyfans_paid
    stash = FakeStash(images=[str(media_dir / f"{m}.jpg") for m in (2001, 4001, 6001)])
    sync([db], stash, apply=True)
    assert by_file(stash, "2001.jpg")["urls"] == [f"https://onlyfans.com/1001/{OF_USER}"]
    assert by_file(stash, "4001.jpg")["urls"] == []  # a message, also bought
    # only bought, but the purchase type says it was a post
    assert by_file(stash, "6001.jpg")["urls"] == [f"https://onlyfans.com/5001/{OF_USER}"]
    assert by_file(stash, "4001.jpg")["code"] == "3001"


# --- the columns added in #315: posts.purchase_type, messages.group_id, posts.mentions


def run_log(db, files):
    """Sync one database into a new FakeStash; return everything sent and the end state."""
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    preview = sync([db], stash)
    sync([db], stash, apply=True)
    again = sync([db], stash, apply=True)
    return {
        "reports": (preview["totals"], again["totals"]),
        "created": stash.created,
        "updates": stash.updates,
        "items": {Path(i["path"]).name: named(stash, i) for kind in stash.items.values() for i in kind.values()},
        "galleries": {g["code"]: named(stash, g) for g in stash.galleries.values()},
    }


def clear_columns(db, drop=False):
    """Empty the new columns, as on rows saved before them, or drop them (the older layout)."""
    with closing(sqlite3.connect(db)) as conn, conn:
        for table, column in (("posts", "purchase_type"), ("posts", "mentions"), ("messages", "group_id")):
            if drop:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
            else:
                conn.execute(f"UPDATE {table} SET {column} = NULL")


def test_onlyfans_purchase_type_links_only_bought_posts(onlyfans_paid):
    db, media_dir = onlyfans_paid
    with closing(sqlite3.connect(db)) as conn:
        assert dict(conn.execute("SELECT post_id, purchase_type FROM posts")) == {1001: None, 3001: "message", 5001: "post"}
    files = [(str(media_dir / f"{m}.jpg"), "image") for m in (2001, 4001, 6001)]
    log = run_log(db, files)
    assert log["items"]["6001.jpg"]["urls"] == [f"https://onlyfans.com/5001/{OF_USER}"]
    assert log["items"]["4001.jpg"]["urls"] == []  # bought message: no public page
    assert log["items"]["2001.jpg"]["urls"] == [f"https://onlyfans.com/1001/{OF_USER}"]
    assert log["reports"][1] == {"files": 3, "up_to_date": 3}


@pytest.mark.parametrize("drop", [False, True], ids=["null", "older-layout"])
def test_onlyfans_without_purchase_type_syncs_as_before(onlyfans_paid, drop):
    db, media_dir = onlyfans_paid
    files = [(str(media_dir / f"{m}.jpg"), "image") for m in (2001, 4001, 6001)]
    clear_columns(db, drop)
    log = run_log(db, files)
    # as before #315: a post seen only as a purchase can't be told from a message
    assert log["items"]["6001.jpg"]["urls"] == []
    assert log["items"]["4001.jpg"]["urls"] == []
    assert log["items"]["2001.jpg"]["urls"] == [f"https://onlyfans.com/1001/{OF_USER}"]


def test_onlyfans_bought_message_with_post_purchase_type_still_gets_no_link(library):
    # a bought message is also in messages; that wins over a purchase type
    db, media_dir = library
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO posts (post_id, text, model_id, purchase_type) VALUES (2002, 'bought', 123, 'post')")
    stash = FakeStash(images=[str(media_dir / "msg.jpg")])
    sync([db], stash, apply=True)
    assert by_file(stash, "msg.jpg")["urls"] == []


def test_fansly_message_gets_its_conversation_link(fansly_library):
    db, _, files = fansly_library
    with closing(sqlite3.connect(db)) as conn:
        assert dict(conn.execute("SELECT post_id, group_id FROM messages")) == {
            MESSAGE: str(GROUP), 100000000000000147: str(GROUP)}
    log = run_log(db, files)
    # both messages are in one conversation, so they share its link
    assert log["galleries"][str(MESSAGE)]["urls"] == [MESSAGE_URL]
    assert log["galleries"][str(OTHER_MESSAGE)]["urls"] == [MESSAGE_URL]
    assert log["items"]["100000000000000229.jpg"]["urls"] == [MESSAGE_URL]
    sent = json.dumps(log["created"] + log["updates"])
    assert f"/messages/{GROUP}/" not in sent
    # posts keep their post link
    assert log["galleries"][str(MENTION_POST)]["urls"] == [f"https://fansly.com/post/{MENTION_POST}"]
    assert log["reports"][0]["galleries_to_create"] == 5
    assert "updated" not in log["reports"][1] and "galleries_created" not in log["reports"][1]


@pytest.mark.parametrize("drop", [False, True], ids=["null", "older-layout"])
def test_fansly_without_new_columns_syncs_as_before(make_fansly, tmp_path, drop):
    db, _, files = make_fansly()
    with_values = run_log(db, files)
    clear_columns(db, drop)
    log = run_log(db, files)
    assert all(g["urls"] == [] for code, g in log["galleries"].items() if code in (str(MESSAGE), "100000000000000147"))
    assert log["items"]["100000000000000229.jpg"]["urls"] == []
    # the conversation link is the only difference
    for found in (log, with_values):
        for meta in list(found["items"].values()) + list(found["galleries"].values()):
            meta["urls"] = [u for u in meta["urls"] if "/messages/" not in u]
    assert log["items"] == with_values["items"] and log["galleries"] == with_values["galleries"]


def test_fansly_message_link_is_added_to_a_gallery_made_before(fansly_library, tmp_path):
    # a run before the conversation id was saved made the message's gallery without
    # a link; once a scan fills it in, the next run adds the link to that gallery
    db, _, files = fansly_library
    with closing(sqlite3.connect(db)) as conn:
        groups = list(conn.execute("SELECT post_id, group_id FROM messages"))
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    clear_columns(db)
    sync([db], stash, apply=True)
    assert len(stash.galleries) == 5
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.executemany("UPDATE messages SET group_id = ? WHERE post_id = ?", [(g, p) for p, g in groups])
    report = sync([db], stash, apply=True)
    assert len(stash.galleries) == 5 and "galleries_created" not in report["totals"]
    assert report["totals"]["galleries_updated"] == 2
    gallery = next(g for g in stash.galleries.values() if g["code"] == str(MESSAGE))
    assert gallery["urls"] == [MESSAGE_URL]
    assert by_file(stash, "100000000000000229.jpg")["urls"] == [MESSAGE_URL]


@pytest.mark.parametrize("group", ["", "1_%", "../x"])
def test_fansly_conversation_id_that_is_not_a_number_gives_no_link(fansly_library, group):
    db, _, files = fansly_library
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE messages SET group_id = ?", (group,))
    log = run_log(db, files)
    assert log["galleries"][str(MESSAGE)]["urls"] == []
    assert log["items"]["100000000000000229.jpg"]["urls"] == []


def test_fansly_old_message_link_is_replaced_and_other_links_kept(fansly_library, tmp_path):
    # a file and galleries synced by #356 have the old .../<conversation>/<message>
    # link, beside links the user added; only that exact old link goes
    db, _, files = fansly_library
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    mine = "https://example.com/my-notes"
    other_old = f"https://fansly.com/messages/{GROUP}/{OTHER_MESSAGE}"  # another message's, not this one's
    unrelated = "https://fansly.com/messages/x/y"
    wildcard = f"https://fansly.com/messages/{GROUP}/{str(MESSAGE)[:-1]}_"  # equal only under LIKE
    item = by_file(stash, "100000000000000229.jpg")
    item["urls"] = [mine, OLD_MESSAGE_URL, other_old, unrelated, wildcard]
    blank = {"title": "", "details": "", "date": None, "organized": False, "studio": None, "performers": [],
             "tags": []}
    stash.galleries["g1"] = {**blank, "id": "g1", "code": str(MESSAGE), "urls": [OLD_MESSAGE_URL, mine]}
    # already has the new link too: the old one is only dropped
    stash.galleries["g2"] = {**blank, "id": "g2", "code": str(OTHER_MESSAGE), "urls": [other_old, MESSAGE_URL]}

    report = sync([db], stash, apply=True)

    assert item["urls"] == [mine, other_old, unrelated, wildcard, MESSAGE_URL]
    assert stash.galleries["g1"]["urls"] == [mine, MESSAGE_URL]
    assert stash.galleries["g2"]["urls"] == [MESSAGE_URL]
    assert {"id": "g1"} in item["galleries"]  # the galleries are reused, not made again
    assert len(stash.galleries) == 5 and report["totals"]["galleries_created"] == 3

    # a second run changes nothing more
    updates, created = len(stash.updates), len(stash.created)
    again = sync([db], stash, apply=True)
    assert (len(stash.updates), len(stash.created)) == (updates, created)
    assert "updated" not in again["totals"] and "galleries_updated" not in again["totals"]
    assert item["urls"] == [mine, other_old, unrelated, wildcard, MESSAGE_URL]


@pytest.mark.parametrize("stored", ["[]", json.dumps([{"listed": "listedonly"}]), "not json"])
def test_fansly_stored_mentions_dont_change_performers(make_fansly, stored):
    # Which field of an accountMentions entry holds the username isn't known
    # from a real post, so the caption's @name stays the source; a stored list,
    # even an empty one, neither adds nor drops a performer
    db, _, files = make_fansly()
    before = run_log(db, files)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE posts SET mentions = ?", (stored,))
    after = run_log(db, files)
    assert after["items"] == before["items"] and after["created"] == before["created"]
    assert FRIEND in after["items"]["100000000000000026.mp4"]["performers"]
    assert "listedonly" not in json.dumps(after["created"])


def test_onlyfans_and_fansly_together(library, make_fansly, tmp_path):
    of_db, of_dir = library
    with closing(sqlite3.connect(of_db)) as conn, conn:
        conn.execute("INSERT INTO posts (post_id, text, model_id, purchase_type) VALUES (3003, 'bought post', 123, 'post')")
        conn.execute("INSERT INTO posts (post_id, text, model_id, purchase_type) VALUES (3004, 'bought msg', 123, 'message')")
        conn.execute("INSERT INTO posts (post_id, text, model_id) VALUES (3005, 'unknown purchase', 123)")
        for media_id, post_id, name in ((7, 3003, "bought_post.jpg"), (8, 3004, "bought_msg.jpg"), (9, 3005, "bought.jpg")):
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, api_type, media_type, downloaded, "
                "posted_at, created_at, model_id) VALUES (?,?,?,?,'Paid','Images',1,?,?,123)",
                (media_id, post_id, str(of_dir), name, "2025-03-01T10:00:00+00:00", "2025-03-01T10:00:00+00:00"))
    _, _, fansly_files = make_fansly()
    stash = FakeStash()
    for path, kind in fansly_files:
        stash.add(kind, path)
    for name in ("post.jpg", "bought_post.jpg", "bought_msg.jpg", "bought.jpg"):
        stash.add("image", str(of_dir / name))

    sync([tmp_path / ".data"], stash, apply=True)
    assert by_file(stash, "bought_post.jpg")["urls"] == ["https://onlyfans.com/3003/creator"]
    assert by_file(stash, "bought_msg.jpg")["urls"] == []
    assert by_file(stash, "bought.jpg")["urls"] == []
    assert by_file(stash, "post.jpg")["urls"] == ["https://onlyfans.com/1001/creator"]
    assert by_file(stash, "100000000000000229.jpg")["urls"] == [MESSAGE_URL]
    assert by_file(stash, "100000000000000026.mp4")["urls"] == [f"https://fansly.com/post/{MENTION_POST}"]
    # the OnlyFans studio and tags, and no OnlyFans gallery
    assert named(stash, by_file(stash, "bought_post.jpg"))["studio"] == "OnlyFans"
    assert named(stash, by_file(stash, "bought_post.jpg"))["tags"] == ["OnlyFans Paid"]
    assert all(g["code"] not in ("3003", "3004", "3005") for g in stash.galleries.values())

    report = sync([tmp_path / ".data"], stash, apply=True)
    assert "updated" not in report["totals"] and "galleries_created" not in report["totals"]


def test_mention_with_underscore_gets_its_own_performer(make_fansly, tmp_path):
    # Stash would take "pal_one" for the existing "Pal One", a different person
    _, _, files = make_fansly(edits={MENTION_POST: "{} @pal_one"})
    stash = FakeStash()
    for path, kind in files:
        stash.add(kind, path)
    other = stash.entity("performer", "Pal One")

    sync([tmp_path / ".data"], stash, apply=True)
    created = [v for kind, v in stash.created if kind == "performer" and v["name"] == "pal_one"]
    assert created == [{"name": "pal_one", "urls": ["https://fansly.com/pal_one"], "disambiguation": "Fansly"}]
    pal = stash.entities["performer"]["pal_one"]
    item = by_file(stash, "100000000000000026.mp4")
    assert {"id": pal} in item["performers"] and {"id": other} not in item["performers"]

    # found again by its exact name: nothing new
    before = len(stash.created)
    report = sync([tmp_path / ".data"], stash, apply=True)
    assert len(stash.created) == before and "updated" not in report["totals"]


def test_onlyfans_creator_with_underscore_gets_its_own_performer(library):
    db, media_dir = library
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE profiles SET username = 'the_creator'")
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")])
    other = stash.entity("performer", "The Creator")
    sync([db], stash, apply=True)
    created = [v for kind, v in stash.created if kind == "performer"]
    assert created == [{"name": "the_creator", "urls": ["https://onlyfans.com/the_creator"], "disambiguation": "OnlyFans"}]
    assert next(iter(stash.items["scene"].values()))["performers"] == [{"id": stash.entities["performer"]["the_creator"]}]
    assert other != stash.entities["performer"]["the_creator"]
    before = len(stash.created)
    sync([db], stash, apply=True)
    assert len(stash.created) == before


@pytest.mark.parametrize("apply", [True, False])
def test_studio_name_stash_would_refuse_stops_before_any_change(library, fansly_library, stash_server, tmp_path,
                                                                 capsys, apply):
    of_db, of_dir = library
    _, _, fansly_files = fansly_library
    stash, url = stash_server
    for path, kind in fansly_files:
        stash.add(kind, path)
    stash.add("scene", str(of_dir / "post.mp4"))
    stash.entity("studio", "My Studio")
    args = [str(tmp_path / ".data"), "--url", url, "--studio", "My_Studio"] + (["--apply"] if apply else [])
    assert stash_sync.main(args) == 1
    assert "wildcards" in capsys.readouterr().err
    # nothing was created or changed: no performers, tags, galleries or item updates
    assert stash.mutations == []
    assert all(not item["performers"] for kind in stash.items.values() for item in kind.values())


@pytest.mark.parametrize("studio", ["My Studio", "my studio", "Mine", "My Other Studio"])
def test_usable_studio_is_set(library, studio):
    db, media_dir = library
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")])
    mine = stash.entity("studio", "My Studio", aliases=["Mine"])
    report = sync([db], stash, apply=True, studio=studio)
    assert report["totals"]["updated"] == 1
    item = next(iter(stash.items["scene"].values()))
    created = [new for kind, new in stash.created if kind == "studio"]
    if studio == "My Other Studio":
        assert [new["name"] for new in created] == [studio]
        assert item["studio"] == {"id": stash.entities["studio"][studio]}
    else:
        assert created == []
        assert item["studio"] == {"id": mine}


def test_onlyfans_performer_in_another_case_is_reused(library):
    db, media_dir = library
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")])
    creator = stash.entity("performer", "Creator")
    report = sync([db], stash, apply=True)
    assert report["totals"]["updated"] == 1
    assert next(iter(stash.items["scene"].values()))["performers"] == [{"id": creator}]
    assert "performer" not in {kind for kind, _ in stash.created}


def test_site_flag_is_read_in_any_case(tmp_path):
    db = tmp_path / "user_data.db"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(schemaCreate)
        conn.execute(siteInsert, ("Fansly",))
    assert stash_sync.site_of(db) == "fansly"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DELETE FROM schema_flags")
    assert stash_sync.site_of(db) == "onlyfans"


def test_mentions():
    text = "hi @friend_1 and @Friend_1, mail me@example.com, see @other. and @creator"
    assert stash_sync.mentions(text, "Creator") == ["friend_1", "other"]


def test_no_tags(library):
    db, media_dir = library
    stash = FakeStash(scenes=[str(media_dir / "post.mp4")])
    sync([db], stash, apply=True, tags=False)
    assert stash.entities["tag"] == {}


def test_unreachable_stash_exits_with_error(library, capsys):
    db, _ = library
    assert stash_sync.main([str(db), "--url", "http://127.0.0.1:9/graphql"]) == 1
    assert "can't reach Stash" in capsys.readouterr().err


def test_locked_database_is_retried(monkeypatch):
    replies = iter([
        b'{"errors": [{"message": "beginning transaction: database is locked"}], "data": null}',
        b'{"data": {"ok": true}}',
    ])

    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.body

    monkeypatch.setattr(stash_sync.urllib.request, "urlopen", lambda *a, **k: Response(next(replies)))
    monkeypatch.setattr(stash_sync.time, "sleep", lambda s: None)
    assert stash_sync.StashClient().call("{ ok }") == {"ok": True}


def test_graphql_errors_are_raised(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"errors": [{"message": "bad field"}]}'

    monkeypatch.setattr(stash_sync.urllib.request, "urlopen", lambda *a, **k: Response())
    with pytest.raises(StashError, match="bad field"):
        stash_sync.StashClient().call("{ x }")
