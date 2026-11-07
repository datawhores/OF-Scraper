"""Fansly posts, messages and media: API paging, conversion and database writes.

The fixtures in ``test/fixtures/fansly`` are anonymised captures: every id,
name, text and URL is fake. No request is sent anywhere; a fake session
answers each API path from the fixtures.
"""

import asyncio
import contextlib
import copy
import json
import pathlib
import sqlite3
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import arrow
import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.posts.post as post
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.sites.fansly import api, constants, normalize, scrape

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "fansly"

CREATOR_ID = 100000000000000002
CREATOR = "samplecreator1"
BUNDLE_POST = 100000000000000004
LOCKED_POST = 100000000000000006
BUNDLE_IDS = ["100000000000000003"] + [f"1000000000000000{n:02d}" for n in range(8, 19)]
NOT_EMBEDDED = BUNDLE_IDS[5:]

DM_CREATOR_ID = 100000000000000053
DM_CREATOR = "samplecreator2"
GROUP_ID = "100000000000000143"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def envelope(response):
    return {"success": True, "response": response}


class FakeResponse:
    def __init__(self, data):
        self._data = data
        self.status_code = 200

    async def json_(self):
        return copy.deepcopy(self._data)


class FakeSession:
    """Answers API paths from a routing function and records every URL."""

    def __init__(self, route):
        self.route = route
        self.urls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        self.urls.append(url)
        parsed = urlparse(url)
        path = parsed.path[len(urlparse(constants.API_BASE).path):]
        query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
        yield FakeResponse(self.route(path, query))

    def calls(self, path):
        out = []
        for url in self.urls:
            parsed = urlparse(url)
            if parsed.path.endswith("/" + path):
                out.append({k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()})
        return out


def timeline_route(path, query):
    if path == f"timelinenew/{CREATOR_ID}":
        if query["before"] == "0":
            return load("timeline.json")
        return envelope({"posts": [], "accountMedia": [], "accountMediaBundles": []})
    if path == "account/media":
        wanted = query["ids"].split(",")
        media = load("timeline_missing_media.json")["response"]
        return envelope([m for m in media if m["id"] in wanted])
    raise AssertionError(f"unexpected Fansly call {path}")


def messages_route(path, query):
    if path == "messaging/groups":
        return load("groups.json")
    if path == "message":
        assert query["groupId"] == GROUP_ID
        if "before" not in query:
            return load("messages.json")
        return envelope({"messages": [], "accountMedia": [], "accountMediaBundles": []})
    if path == "account/media":
        wanted = query["ids"].split(",")
        media = load("messages_missing_media.json")["response"]
        return envelope([m for m in media if m["id"] in wanted])
    raise AssertionError(f"unexpected Fansly call {path}")


@pytest.fixture
def fansly(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(site="fansly", after=None, post_id=None, timeline_strict=False, usernames=None)
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return stub


@contextlib.asynccontextmanager
async def _ctx(c):
    yield c


def by_id(items, item_id):
    return next(x for x in items if x["id"] == item_id)


def iso(seconds):
    return arrow.get(seconds).isoformat()


# ------------------------------------------------------------------ DoD 1


def test_bundle_of_12_gives_all_12_media(fansly):
    c = FakeSession(timeline_route)
    found = asyncio.run(scrape.get_timeline_posts(CREATOR_ID, CREATOR, c=c))

    # the 7 members the response left out came from one account/media call
    assert c.calls("account/media") == [{"ids": ",".join(NOT_EMBEDDED), "ngsw-bypass": "true"}]
    # paging: the second page starts before the last post of the first
    pages = c.calls(f"timelinenew/{CREATOR_ID}")
    assert [p["before"] for p in pages] == ["0", str(LOCKED_POST)]
    assert all(p["wallId"] == "" and p["ngsw-bypass"] == "true" for p in pages)

    bundle_post = by_id(found, BUNDLE_POST)
    assert bundle_post["text"] == "Sample text 2 #weekend #behindthescenes"
    assert bundle_post["hashtags"] == ["weekend", "behindthescenes"]
    assert bundle_post["createdAt"] == iso(1793934243)
    assert [m["fansly"]["accountMediaId"] for m in bundle_post["media"]] == BUNDLE_IDS

    p = posts_.Post(bundle_post, CREATOR_ID, CREATOR, "Timeline")
    assert len(p.media) == 12
    assert {m.post_id for m in p.media} == {BUNDLE_POST}
    assert {m.preview for m in p.media} == {0}
    assert all(m.url and m.url.startswith("https://cdn3.fansly.com/") for m in p.media)
    assert {m.postdate for m in p.media} == {iso(1793934243)}
    # Media ids, not accountMedia ids
    assert {str(m.id) for m in p.media}.isdisjoint(BUNDLE_IDS)
    assert p.responsetype == "Timeline"


def test_media_dict_contract(fansly):
    found = asyncio.run(scrape.get_timeline_posts(CREATOR_ID, CREATOR, c=FakeSession(timeline_route)))
    first = by_id(found, 100000000000000001)["media"][0]
    raw = load("timeline.json")["response"]["accountMedia"][0]["media"]
    assert first["id"] == int(raw["id"])
    assert first["type"] == "video"
    assert first["canView"] is True
    assert first["duration"] == 27  # 26.566667 s, whole seconds like OnlyFans
    assert first["files"]["full"]["url"] == raw["locations"][0]["location"]
    assert first["fansly"] == {
        "accountMediaId": "100000000000000003",
        "mediaId": raw["id"],
        "isPreview": False,
        "media": raw,
    }


# ------------------------------------------------------------------ DoD 2


def test_messages_carry_id_group_sender_and_date(fansly):
    c = FakeSession(messages_route)
    found = asyncio.run(scrape.get_messages(DM_CREATOR_ID, DM_CREATOR, c=c))
    assert c.calls("account/media") == [{"ids": "100000000000000265", "ngsw-bypass": "true"}]
    assert [c_["before"] for c_ in c.calls("message") if "before" in c_] == ["100000000000000147"]

    raw = load("messages.json")["response"]["messages"]
    assert [m["id"] for m in found] == [int(m["id"]) for m in raw]
    for message, source in zip(found, raw):
        assert message["groupId"] == GROUP_ID
        assert message["fromUser"] == {"id": DM_CREATOR_ID}
        assert message["createdAt"] == iso(source["createdAt"])
        p = posts_.Post(message, DM_CREATOR_ID, DM_CREATOR)
        assert p.responsetype == "Messages"
        assert p.fromuser == DM_CREATOR_ID
        assert p.all_media and {m.post_id for m in p.all_media} == {int(source["id"])}
        assert {m.postdate for m in p.all_media} == {iso(source["createdAt"])}

    # bundle of 4 plus one single item, then a bundle of 6 (one fetched)
    assert len({m["fansly"]["accountMediaId"] for m in found[0]["media"]}) == 5
    assert len({m["fansly"]["accountMediaId"] for m in found[1]["media"]}) == 6
    assert found[1]["price"] == pytest.approx(9.99)


def test_messages_from_me_are_not_downloaded(fansly):
    found = asyncio.run(scrape.get_messages(DM_CREATOR_ID, DM_CREATOR, c=FakeSession(messages_route)))
    sent_by_me = posts_.Post(found[0], 100000000000000146, "me")
    assert sent_by_me.media == []


def test_no_conversation_means_no_messages(fansly):
    c = FakeSession(messages_route)
    assert asyncio.run(scrape.get_messages(999, "nobody", c=c)) == []
    assert c.calls("message") == []


# ------------------------------------------------------------------ DoD 3


def test_locked_item_with_preview(fansly):
    found = asyncio.run(scrape.get_timeline_posts(CREATOR_ID, CREATOR, c=FakeSession(timeline_route)))
    locked = by_id(found, LOCKED_POST)
    assert locked["price"] == pytest.approx(9.99)
    assert locked["isOpened"] is False
    full, preview = locked["media"]
    assert (full["id"], full["canView"], full["files"]["full"]["url"]) == (100000000000000050, False, None)
    assert full["fansly"]["isPreview"] is False
    assert (preview["id"], preview["canView"]) == (100000000000000051, True)
    assert preview["fansly"]["isPreview"] is True
    assert preview["fansly"]["accountMediaId"] == full["fansly"]["accountMediaId"] == "100000000000000007"

    p = posts_.Post(locked, CREATOR_ID, CREATOR, "Timeline")
    full_m, preview_m = p.all_media
    assert (full_m.canview, full_m.preview, full_m.url) == (False, 0, None)
    assert (preview_m.canview, preview_m.preview) == (True, 1)
    assert preview_m.url.startswith("https://cdn3.fansly.com/")
    assert [m.id for m in p.media] == [100000000000000051]


def test_unlocked_item_ignores_its_preview():
    account_media = load("timeline_missing_media.json")["response"][-1]
    assert account_media["access"] is True and account_media["previewId"]
    out = normalize.media_for(account_media)
    assert [m["fansly"]["isPreview"] for m in out] == [False]


# ------------------------------------------------------------------ DoD 4


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    # surface errors the area functions would otherwise only log
    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    monkeypatch.setattr(post.log, "traceback_", fail, raising=False)
    return db


def table_rows(db):
    out = {}
    with contextlib.closing(sqlite3.connect(db)) as conn:
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            out[name] = sorted(conn.execute(f"SELECT * FROM {name}").fetchall(), key=repr)
    return out


async def scrape_once(model_id, username, route):
    c = FakeSession(route)
    await operations.table_init_create(model_id=model_id, username=username)
    timeline_posts, _ = await post.process_timeline_posts(model_id, username, c)
    messages_, _ = await post.process_messages(model_id, username, c)
    media = [m for p in timeline_posts + messages_ for m in p.all_media]
    await batch_mediainsert(media, model_id=model_id, username=username, downloaded=False)


def both_routes(path, query):
    """One creator with the timeline fixture and the message fixture."""
    if path.startswith("timelinenew/"):
        return timeline_route(f"timelinenew/{CREATOR_ID}", query)
    if path == "account/media":
        wanted = query["ids"].split(",")
        media = load("timeline_missing_media.json")["response"]
        media += load("messages_missing_media.json")["response"]
        return envelope([m for m in media if m["id"] in wanted])
    return messages_route(path, query)


def test_same_fixture_twice_adds_nothing(fansly, tmp_db):
    asyncio.run(scrape_once(DM_CREATOR_ID, DM_CREATOR, both_routes))
    first = table_rows(tmp_db)
    assert len(first["posts"]) == 3
    assert len(first["messages"]) == 2
    # timeline: 1 + 12 + (locked item and its preview) 2;
    # messages: 5 items with 3 previews, 6 items with 2 previews
    assert len(first["medias"]) == 15 + 8 + 8
    asyncio.run(scrape_once(DM_CREATOR_ID, DM_CREATOR, both_routes))
    assert table_rows(tmp_db) == first


def test_rows_written_for_messages_and_previews(fansly, tmp_db):
    asyncio.run(scrape_once(DM_CREATOR_ID, DM_CREATOR, both_routes))
    with contextlib.closing(sqlite3.connect(tmp_db)) as conn:
        messages_ = conn.execute(
            "SELECT post_id, user_id, created_at, price FROM messages ORDER BY post_id"
        ).fetchall()
        preview = conn.execute(
            "SELECT post_id, preview, linked, unlocked FROM medias WHERE media_id = ?",
            (100000000000000051,),
        ).fetchone()
        locked = conn.execute(
            "SELECT post_id, preview, linked, unlocked, link FROM medias WHERE media_id = ?",
            (100000000000000050,),
        ).fetchone()
    raw = load("messages.json")["response"]["messages"]
    assert messages_ == sorted(
        (int(m["id"]), DM_CREATOR_ID, iso(m["createdAt"]), 9.99) for m in raw
    )
    assert preview == (LOCKED_POST, 1, 1, 1)
    assert locked == (LOCKED_POST, 0, 0, 0, None)


def test_fansly_database_records_its_site(fansly, tmp_db):
    from ofscraper.db.operations_.others import get_site_flag

    async def init():
        await operations.table_init_create(model_id=CREATOR_ID, username=CREATOR)

    asyncio.run(init())
    assert get_site_flag(model_id=CREATOR_ID, username=CREATOR) == "fansly"
    with contextlib.closing(sqlite3.connect(tmp_db)) as conn:
        # it is not mistaken for a schema change flag
        assert "site" not in {
            r[0] for r in conn.execute("SELECT flag_name FROM schema_flags WHERE flag_value = 1")
        }


# ------------------------------------------------------------------ routing and paths


def test_fansly_skips_areas_it_does_not_support(fansly, monkeypatch):
    called = []

    async def fake(name):
        called.append(name)
        return [], name

    for name in ["paid_post", "messages", "timeline_posts", "pinned_posts", "archived_posts",
                 "highlights", "stories", "labels", "streamed_posts"]:
        monkeypatch.setattr(post, f"process_{name}", lambda *a, _n=name, **k: fake(_n))
    monkeypatch.setattr(post, "process_profile", lambda *a, **k: fake("profile"))
    monkeypatch.setattr(post, "get_final_posts_area", lambda: [
        "Profile", "Purchased", "Messages", "Pinned", "Timeline", "Archived", "Highlights",
        "Stories", "Labels", "Streams"])
    monkeypatch.setattr(post, "get_like_area", lambda: [])
    monkeypatch.setattr(post, "get_download_area", lambda: [])
    monkeypatch.setattr(post.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    ele = SimpleNamespace(active=True)
    asyncio.run(post.process_tasks(CREATOR_ID, CREATOR, ele))
    assert sorted(called) == ["messages", "paid_post", "timeline_posts"]


def test_models_come_from_fansly_accounts(fansly, monkeypatch):
    import ofscraper.data.models.utils.retriver as retriver

    c = FakeSession(lambda path, query: load("account.json"))
    monkeypatch.setattr(scrape, "_session", lambda _c: _ctx(c))
    fansly.usernames = [CREATOR]
    models = asyncio.run(retriver.get_models())
    assert [(m.id, m.name) for m in models] == [(CREATOR_ID, CREATOR)]
    assert c.calls("account") == [{"usernames": CREATOR, "ngsw-bypass": "true"}]


def test_followed_accounts_are_paged_then_resolved(fansly, monkeypatch):
    stubs = [{"accountId": str(100000000000000300 + i)} for i in range(7)]

    def route(path, query):
        if path.endswith("/following"):
            offset, limit = int(query["offset"]), int(query["limit"])
            return envelope(stubs[offset : offset + limit])
        if path == "account":
            return envelope([{"id": i, "username": f"creator{i[-2:]}"} for i in query["ids"].split(",")])
        raise AssertionError(path)

    c = FakeSession(route)
    monkeypatch.setattr(scrape, "_session", lambda _c: _ctx(c))
    monkeypatch.setattr(api, "FOLLOWING_LIMIT", 5)
    import ofscraper.utils.me as me_util

    monkeypatch.setattr(me_util, "get_id", lambda: "100000000000000147")
    models = asyncio.run(scrape.get_models())
    assert [m["id"] for m in models] == [int(s["accountId"]) for s in stubs]
    assert [q["offset"] for q in c.calls("account/100000000000000147/following")] == ["0", "5"]
    assert [len(q["ids"].split(",")) for q in c.calls("account")] == [5, 2]


def test_account_media_is_fetched_150_at_a_time():
    ids = [str(100000000000001000 + i) for i in range(301)]
    c = FakeSession(lambda path, query: envelope([{"id": i} for i in query["ids"].split(",")]))
    out = asyncio.run(api.account_media(c, ids))
    assert [x["id"] for x in out] == ids
    assert [len(q["ids"].split(",")) for q in c.calls("account/media")] == [150, 150, 1]


def test_purchases_become_paid_posts_of_that_creator():
    messages_ = load("messages.json")["response"]
    response = {
        "accountMediaOrders": [
            {"accountMediaId": "100000000000000149", "createdAt": 1777913614},
            {"accountMediaId": "100000000000000999"},
        ],
        "accountMedia": messages_["accountMedia"],
    }
    found = normalize.purchases(response, DM_CREATOR_ID)
    assert [p["id"] for p in found] == [100000000000000149]
    assert found[0]["createdAt"] == iso(1777913614)
    assert found[0]["price"] == pytest.approx(9.99)
    assert normalize.purchases(response, 1) == []
    assert normalize.missing_account_media_ids(response) == ["100000000000000999"]


@pytest.mark.parametrize(
    "value,expected",
    [(1793394484, 1793394484.0), (1793394484433, 1793394484.433), ("1793394484", 1793394484.0),
     (None, None)],
)
def test_seconds_or_milliseconds(value, expected):
    assert normalize.to_seconds(value) == expected


def test_hashtags_are_parsed_from_the_text():
    assert normalize.hashtags("a #One ##two #one b#three #") == ["one", "two", "three"]


def test_price_comes_from_permission_metadata():
    item = {"price": 0, "permissions": {"permissionFlags": [
        {"price": 5000, "metadata": json.dumps({"1": json.dumps({"price": 39690})})}]}}
    assert normalize.price_mills(item) == 39690
    assert normalize.price_mills({"price": 5000}) == 0


@pytest.fixture
def path_env(monkeypatch, tmp_path):
    async def fake_common(self, ele, username, model_id):
        self._variables.update({"model_username": username, "response_type": "Timeline",
                                "media_type": "Videos"})

    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.Placeholders, "add_common_variables", fake_common)
    monkeypatch.setattr(placeholder.Textholders, "add_common_variables", fake_common)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(placeholder.common_paths, "get_save_location",
                        lambda *a, **k: str(tmp_path / "data"))
    monkeypatch.setattr(placeholder.data, "get_dirformat",
                        lambda *a, **k: "{model_username}/{response_type}/{media_type}/")
    return tmp_path


@pytest.mark.parametrize("cls", ["Placeholders", "Textholders"])
def test_fansly_files_go_under_a_fansly_folder(fansly, path_env, cls):
    holder = getattr(placeholder, cls)(SimpleNamespace(username=CREATOR, model_id=CREATOR_ID), "mp4")
    path = asyncio.run(holder.getmediadir(create=False))
    assert pathlib.Path(path) == path_env / "data" / "Fansly" / CREATOR / "Timeline" / "Videos"
    # an explicit root (the temp folder) is left alone
    path = asyncio.run(holder.getmediadir(root=path_env / "tmp", create=False))
    assert pathlib.Path(path) == path_env / "tmp" / CREATOR / "Timeline" / "Videos"


# ------------------------------------------------------------------ review fixes


@pytest.mark.parametrize(
    "fmt", ["{save_location}/{model_username}/metadata", "{root}/{model_username}/metadata"]
)
def test_fansly_database_is_not_the_onlyfans_one(fansly, path_env, monkeypatch, fmt):
    # the same username on both sites must not share a user_data.db
    monkeypatch.setattr(placeholder.data, "get_metadata", lambda *a, **k: fmt)
    fansly_db = placeholder.databasePlaceholder().databasePathHelper(CREATOR_ID, CREATOR)
    fansly.site = "onlyfans"
    onlyfans_db = placeholder.databasePlaceholder().databasePathHelper(CREATOR_ID, CREATOR)
    assert fansly_db == path_env / "data" / "Fansly" / CREATOR / "metadata" / "user_data.db"
    assert onlyfans_db == path_env / "data" / CREATOR / "metadata" / "user_data.db"


def test_fansly_default_database_path_is_unchanged(fansly, path_env, monkeypatch):
    monkeypatch.setattr(placeholder.data, "get_metadata",
                        lambda *a, **k: "{configpath}/{profile}/.data/{model_id}")
    path = placeholder.databasePlaceholder().databasePathHelper(CREATOR_ID, CREATOR)
    assert path == path_env / "cfg" / "main_profile" / ".data" / str(CREATOR_ID) / "user_data.db"


@pytest.mark.parametrize(
    "fmt", ["{configpath}/{profile}/.data/{model_username}", "ABS/{model_username}/meta"]
)
def test_fansly_database_without_a_site_placeholder_is_separate(fansly, path_env, monkeypatch,
                                                                 fmt):
    # a format with nothing site-specific resolves to one folder for both sites
    fmt = fmt.replace("ABS", str(path_env / "abs"))
    monkeypatch.setattr(placeholder.data, "get_metadata", lambda *a, **k: fmt)
    fansly_db = placeholder.databasePlaceholder().databasePathHelper(CREATOR_ID, CREATOR)
    fansly.site = "onlyfans"
    onlyfans_db = placeholder.databasePlaceholder().databasePathHelper(CREATOR_ID, CREATOR)
    assert fansly_db != onlyfans_db
    assert fansly_db == onlyfans_db.parent / "Fansly" / "user_data.db"


def test_saving_files_message_shows_the_fansly_folder(fansly, path_env, monkeypatch):
    from ofscraper.commands.scraper.actions.download import download

    monkeypatch.setattr(download.config_data, "get_dirformat", lambda *a, **k: "{model_username}/x")
    monkeypatch.setattr(download.config_data, "get_fileformat", lambda *a, **k: "f.{ext}")
    shown = download.save_path_str(CREATOR, CREATOR_ID)
    assert str(path_env / "data" / "Fansly" / CREATOR / "x" / "f.{ext}") in shown


def priced(item_id, dollars):
    flag = {"metadata": json.dumps({"1": json.dumps({"price": dollars * 1000})})}
    return {"id": item_id, "permissions": {"permissionFlags": [flag]}}


def test_unpriced_bundle_counts_every_member():
    bundle = {"id": "b1"}
    pairs = [(priced("a1", 1), bundle), (priced("a2", 2), bundle), (priced("a3", 3), bundle)]
    assert normalize._price(pairs) / 1000 == 6.0


def test_priced_bundle_counts_once():
    bundle = priced("b1", 5)
    pairs = [(priced("a1", 1), bundle), (priced("a2", 2), bundle), (priced("a3", 3), None)]
    assert normalize._price(pairs) / 1000 == 8.0


def test_following_stops_when_a_page_repeats(fansly):
    # a server that ignores offset returns the same full page every time
    page = [{"accountId": str(100000000000000300 + i)} for i in range(api.FOLLOWING_LIMIT)]
    c = FakeSession(lambda path, query: envelope(page))
    out = asyncio.run(api.following_ids(c, "1"))
    assert out == [p["accountId"] for p in page]
    assert len(c.urls) == 2


def test_groups_stop_when_a_page_repeats(fansly):
    data = [{"groupId": str(100000000000000400 + i)} for i in range(api.GROUPS_LIMIT)]
    c = FakeSession(lambda path, query: envelope({"data": data}))
    pages = asyncio.run(api.groups(c))
    assert len(pages) == 1
    assert len(c.urls) == 2