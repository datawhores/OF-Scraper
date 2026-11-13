"""Fansly walls as labels (``-o labels``, ``labels+``, ``labels*``).

A Fansly wall is a named tab on a creator's profile. The account object lists
them under ``walls``; a wall's posts come from the timeline endpoint with its
``wallId``. They go through the same label code as OnlyFans labels
(``ofscraper/data/api/labels.py``), so folders, the database and downloads
behave the same. The fixtures are anonymised: every id and name is fake, and
a fake session answers each request.
"""

import asyncio
import contextlib
import copy
import pathlib
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.classes.labels as label_class
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.api.labels as labels_api
import ofscraper.data.posts.post as post
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings
from ofscraper.sites.fansly import normalize, scrape

from test_fansly_api import (
    BUNDLE_POST,
    CREATOR,
    CREATOR_ID,
    LOCKED_POST,
    FakeSession,
    envelope,
    load,
    timeline_route,
)

MAIN_WALL = "100000000000000500"
WALL_ONE = "100000000000000501"
WALL_TWO = "100000000000000502"
FIRST_POST = 100000000000000001
# which timeline fixture posts each wall holds
WALL_POSTS = {WALL_ONE: {BUNDLE_POST, LOCKED_POST}, WALL_TWO: {FIRST_POST}}
ALL_POSTS = {FIRST_POST, BUNDLE_POST, LOCKED_POST}


def walls_fixture():
    return load("account_walls.json")["response"][0]["walls"]


def only_posts(response, ids):
    response = copy.deepcopy(response)
    response["response"]["posts"] = [
        p for p in response["response"]["posts"] if int(p["id"]) in ids
    ]
    return response


def make_route(walls=None, wall_posts=None, fail_wall=None):
    """Account with walls; the timeline answered per ``wallId``."""
    walls = walls_fixture() if walls is None else walls
    wall_posts = WALL_POSTS if wall_posts is None else wall_posts

    def route(path, query):
        if path == "account":
            assert query["ids"] == str(CREATOR_ID)
            account = load("account_walls.json")
            account["response"][0]["walls"] = walls
            return account
        if path == f"timelinenew/{CREATOR_ID}":
            wall = query.get("wallId", "")
            if wall and wall == fail_wall:
                raise RuntimeError("HTTP 500")
            if wall in ("", MAIN_WALL):
                return timeline_route(path, query)
            if query["before"] != "0":
                return envelope({"posts": [], "accountMedia": [], "accountMediaBundles": []})
            return only_posts(load("timeline.json"), wall_posts.get(wall, set()))
        return timeline_route(path, query)

    return route


@pytest.fixture
def fansly(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(site="fansly", after=None, post_id=None, timeline_strict=False,
                usernames=None, label=None, metadata=None)
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return stub


class FakeCache:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None, **kwargs):
        return self.data.get(key, default)

    def set(self, key, value, **kwargs):
        self.data[key] = value


@pytest.fixture(autouse=True)
def isolated_labels(monkeypatch):
    monkeypatch.setattr(labels_api, "cache", FakeCache())
    monkeypatch.setattr(labels_api, "update_check", lambda *a, **k: None)

    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    monkeypatch.setattr(post.log, "traceback_", fail, raising=False)
    labels_api._finished_labels.clear()
    yield
    labels_api._finished_labels.clear()


def wall_calls(c):
    return [q.get("wallId", "") for q in c.calls(f"timelinenew/{CREATOR_ID}")]


async def fetch_labels(c, username=None):
    # get_labels is wrapped by @run; inside a running loop it returns the coroutine
    return await labels_api.get_labels(CREATOR_ID, c=c, username=username)


# ------------------------------------------------------------------ walls -> labels


def test_walls_become_labels_named_after_the_wall():
    assert normalize.labels(walls_fixture()) == [
        {"id": int(WALL_ONE), "name": "Sample wall one", "type": "wall"},
        {"id": int(WALL_TWO), "name": "Sample wall two", "type": "wall"},
    ]


def test_main_posts_wall_is_not_a_label():
    found = normalize.labels(walls_fixture())
    assert int(MAIN_WALL) not in {x["id"] for x in found}
    # without the flags, the wall at position 0 is the main one
    unflagged = [
        {k: v for k, v in w.items() if k not in ("mainWall", "defaultWall")}
        for w in walls_fixture()
    ]
    assert [x["id"] for x in normalize.labels(unflagged)] == [int(WALL_ONE), int(WALL_TWO)]
    # a flagged main wall wins over position 0
    moved = copy.deepcopy(walls_fixture())
    for w in moved:
        w["pos"] = {MAIN_WALL: 2, WALL_ONE: 0, WALL_TWO: 1}[w["id"]]
    assert [x["id"] for x in normalize.labels(moved)] == [int(WALL_ONE), int(WALL_TWO)]


def test_account_without_a_main_wall_keeps_its_first_wall(fansly):
    # hasMainWall false: the wall at position 0 is a topic wall, not "Posts"
    topic = [
        {"id": WALL_ONE, "pos": 0, "name": "Sample wall one"},
        {"id": WALL_TWO, "pos": 1, "name": "Sample wall two"},
    ]
    assert [x["id"] for x in normalize.labels(topic, has_main_wall=False)] == [
        int(WALL_ONE), int(WALL_TWO)]
    # unknown or true: position 0 is the main wall
    assert [x["id"] for x in normalize.labels(topic)] == [int(WALL_TWO)]
    assert [x["id"] for x in normalize.labels(topic, has_main_wall=True)] == [int(WALL_TWO)]

    def route(path, query):
        if path == "account":
            account = load("account_walls.json")
            account["response"][0]["walls"] = topic
            account["response"][0]["hasMainWall"] = False
            return account
        return make_route()(path, query)

    c = FakeSession(route)
    found = asyncio.run(fetch_labels(c))
    assert sorted(x["id"] for x in found) == [int(WALL_ONE), int(WALL_TWO)]


def test_each_wall_is_requested_with_its_wall_id(fansly):
    c = FakeSession(make_route())
    found = asyncio.run(fetch_labels(c))
    assert {x["id"]: (x["name"], {p["id"] for p in x["posts"]}) for x in found} == {
        int(WALL_ONE): ("Sample wall one", WALL_POSTS[WALL_ONE]),
        int(WALL_TWO): ("Sample wall two", WALL_POSTS[WALL_TWO]),
    }
    walls_asked = [w for w in wall_calls(c) if w]
    assert sorted(set(walls_asked)) == [WALL_ONE, WALL_TWO]
    assert MAIN_WALL not in walls_asked
    # no OnlyFans endpoint was called
    assert all("onlyfans.com" not in url for url in c.urls)


def test_label_filter_matches_wall_names(fansly):
    fansly.label = ["sample wall two"]
    c = FakeSession(make_route())
    found = asyncio.run(fetch_labels(c))
    assert [x["id"] for x in found] == [int(WALL_TWO)]
    assert {w for w in wall_calls(c) if w} == {WALL_TWO}


def test_creator_with_only_the_posts_wall_has_no_labels(fansly, tmp_db):
    main_only = [w for w in walls_fixture() if w["id"] == MAIN_WALL]
    c = FakeSession(make_route(walls=main_only))
    assert asyncio.run(fetch_labels(c)) == []
    assert [w for w in wall_calls(c) if w] == []

    async def run():
        await operations.table_init_create(model_id=CREATOR_ID, username=CREATOR)
        return await post.process_labels(CREATOR_ID, CREATOR, c)

    posts, area = asyncio.run(run())
    assert (posts, area) == ([], labels_api.API)


def test_creator_without_walls_has_no_labels(fansly):
    c = FakeSession(make_route(walls=[]))
    assert asyncio.run(fetch_labels(c)) == []


def test_onlyfans_labels_still_use_the_onlyfans_endpoints(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(site="onlyfans")
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    urls = []

    class Response:
        status = 200

        def __init__(self, data):
            self._data = data

        async def json_(self):
            return self._data

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class Client:
        def requests_async(self, url, **kwargs):
            urls.append(url)
            if "/labels?" in url:
                return Response({"list": [{"id": 7, "name": "favourites"}], "hasMore": False})
            return Response({"list": [{"id": 70}], "hasMore": False})

    async def run():
        found = await labels_api.get_labels_data(1, c=Client())
        return await labels_api.get_posts_for_labels(found, 1, c=Client())

    found = asyncio.run(run())
    assert [(x["id"], [p["id"] for p in x["posts"]]) for x in found] == [(7, [70])]
    assert all(u.startswith("https://onlyfans.com/") for u in urls)
    assert "label=7" in urls[-1]


# ------------------------------------------------------------------ repeat scans


def test_repeat_scan_stops_at_a_fully_recorded_page(fansly):
    label = {"id": int(WALL_ONE), "name": "Sample wall one"}

    async def collect(c, known):
        out = []
        async for _, batch in labels_api.scrape_posts_labels(c, label, CREATOR_ID, known=known):
            out.extend(p["id"] for p in batch)
        return out

    full = FakeSession(make_route())
    assert set(asyncio.run(collect(full, None))) == WALL_POSTS[WALL_ONE]
    # first page, then an empty page ends the scan
    assert wall_calls(full) == [WALL_ONE, WALL_ONE]

    repeat = FakeSession(make_route())
    known = {str(i) for i in WALL_POSTS[WALL_ONE]}
    assert set(asyncio.run(collect(repeat, known))) == WALL_POSTS[WALL_ONE]
    assert wall_calls(repeat) == [WALL_ONE]


def test_wall_scan_marks_follow_the_onlyfans_rules(fansly, monkeypatch):
    monkeypatch.setattr(labels_api.log, "traceback_", lambda *a, **k: None, raising=False)
    label = {"id": int(WALL_ONE), "name": "Sample wall one"}
    key = labels_api.label_complete_key(CREATOR_ID, int(WALL_ONE))

    async def drain(c):
        async for _ in labels_api.scrape_posts_labels(c, label, CREATOR_ID, track=True):
            pass

    asyncio.run(drain(FakeSession(make_route())))
    labels_api.commit_finished_labels(CREATOR_ID)
    assert labels_api.cache.data[key] is True

    # an error part way leaves the label to be scanned fully next time
    asyncio.run(drain(FakeSession(make_route(fail_wall=WALL_ONE))))
    labels_api.commit_finished_labels(CREATOR_ID)
    assert labels_api.cache.data[key] is False


# ------------------------------------------------------------------ database and folders


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    return db


def label_rows(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(
            conn.execute("SELECT label_id, name, type, post_id, model_id FROM labels").fetchall()
        )


def post_ids(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return {r[0] for r in conn.execute("SELECT post_id FROM posts")}


def test_label_links_are_written_like_onlyfans_labels(fansly, tmp_db):
    c = FakeSession(make_route())

    async def run():
        await operations.table_init_create(model_id=CREATOR_ID, username=CREATOR)
        return await post.process_labels(CREATOR_ID, CREATOR, c)

    posts, area = asyncio.run(run())
    assert area == labels_api.API
    assert {(p.id, p.label) for p in posts} == {
        (BUNDLE_POST, "Sample wall one"),
        (LOCKED_POST, "Sample wall one"),
        (FIRST_POST, "Sample wall two"),
    }
    assert label_rows(tmp_db) == sorted(
        [(int(WALL_ONE), "Sample wall one", "wall", p, CREATOR_ID) for p in WALL_POSTS[WALL_ONE]]
        + [(int(WALL_TWO), "Sample wall two", "wall", p, CREATOR_ID) for p in WALL_POSTS[WALL_TWO]]
    )
    assert post_ids(tmp_db) == ALL_POSTS
    # a second scan adds nothing
    first = label_rows(tmp_db)
    asyncio.run(run())
    assert label_rows(tmp_db) == first


@pytest.fixture
def path_env(monkeypatch, tmp_path):
    # the same fields add_main_variables reads from the media item
    async def fake_common(self, ele, username, model_id):
        self._variables.update({"model_username": username,
                                "response_type": ele.modified_responsetype,
                                "label": ele.label_string,
                                "media_type": ele.mediatype.capitalize()})
        self.add_no_underline()

    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.Placeholders, "add_common_variables", fake_common)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(placeholder.common_paths, "get_save_location",
                        lambda *a, **k: str(tmp_path / "data"))
    return tmp_path


def media_dir(monkeypatch, media, dir_format):
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: dir_format)
    path = asyncio.run(placeholder.Placeholders(media, "mp4").getmediadir(create=False))
    return pathlib.Path(path)


def labelled_and_timeline_media(c):
    found = asyncio.run(fetch_labels(c))
    wall_one = next(x for x in found if x["id"] == int(WALL_ONE))
    labelled = label_class.Label(wall_one, CREATOR_ID, CREATOR).posts
    labelled = next(p for p in labelled if p.id == BUNDLE_POST).all_media[0]
    timeline = asyncio.run(scrape.get_timeline_posts(CREATOR_ID, CREATOR, c=c))
    timeline = next(p for p in timeline if p["id"] == BUNDLE_POST)
    import ofscraper.classes.of.posts as posts_

    timeline = posts_.Post(timeline, CREATOR_ID, CREATOR, "timeline").all_media[0]
    return labelled, timeline


def test_default_layout_keeps_labelled_files_in_the_timeline_folder(fansly, path_env,
                                                                     monkeypatch):
    # without {label} in dir_format, labels are recorded but don't move files
    labelled, timeline = labelled_and_timeline_media(FakeSession(make_route()))
    fmt = "{model_username}/{responsetype}/{mediatype}/"
    assert media_dir(monkeypatch, labelled, fmt) == media_dir(monkeypatch, timeline, fmt)
    assert media_dir(monkeypatch, labelled, fmt).parent.name == timeline.modified_responsetype


def test_label_placeholder_gives_a_folder_per_wall(fansly, path_env, monkeypatch):
    labelled, timeline = labelled_and_timeline_media(FakeSession(make_route()))
    fmt = "{model_username}/{responsetype}/{label}/{mediatype}/"
    root = path_env / "data" / "Fansly" / CREATOR / timeline.modified_responsetype
    assert media_dir(monkeypatch, labelled, fmt) == root / "Sample wall one" / "Videos"
    # the same post from the timeline has no label
    assert media_dir(monkeypatch, timeline, fmt) == root / "None" / "Videos"


# ------------------------------------------------------------------ area dispatch


def run_areas(monkeypatch, areas, c, active=True):
    monkeypatch.setattr(post, "get_final_posts_area", lambda: set(areas))
    monkeypatch.setattr(post, "get_like_area", lambda: set())
    monkeypatch.setattr(post, "get_download_area", lambda: set(areas))
    monkeypatch.setattr(post.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())

    async def run():
        await operations.table_init_create(model_id=CREATOR_ID, username=CREATOR)
        return await post.process_tasks(CREATOR_ID, CREATOR, SimpleNamespace(active=active), c=c)

    return asyncio.run(run())


@pytest.mark.parametrize("option", ["Labels+", "Labels*"])
def test_labels_plus_and_star_add_labels_to_the_fansly_areas(fansly, monkeypatch, option):
    from ofscraper.utils.args.accessors import areas

    fansly.posts = [option]
    fansly.download_area = []
    fansly.like_area = []
    fansly.actions = ["download"]
    fansly.command = "post_check"
    chosen = areas.get_final_posts_area()
    assert {"Labels", "Timeline", "Messages", "Purchased"} <= chosen
    assert {a for a in chosen if a in scrape.AREAS} == {"Labels", "Timeline", "Messages",
                                                        "Purchased"}


def test_post_in_timeline_and_wall_is_downloaded_once(fansly, tmp_db, monkeypatch):
    fansly.command = "download"
    fansly.text = False
    c = FakeSession(make_route())
    collection = run_areas(monkeypatch, ["Timeline", "Labels"], c)
    assert sorted(p.id for p in collection.posts) == sorted(ALL_POSTS)
    media_ids = [m.id for m in collection.all_unique_media]
    assert len(media_ids) == len(set(media_ids))
    timeline_media = {
        m["id"] for p in asyncio.run(scrape.get_timeline_posts(CREATOR_ID, CREATOR, c=c))
        for m in p["media"]
    }
    assert set(media_ids) == timeline_media
    # the label links are recorded all the same
    assert {r[0] for r in label_rows(tmp_db)} == {int(WALL_ONE), int(WALL_TWO)}


@pytest.mark.parametrize("site", ["fansly", "onlyfans"])
def test_skipped_labels_are_logged_for_inactive_creators(fansly, monkeypatch, site):
    fansly.site = site
    called, infos = [], []

    async def fake_labels(*a, **k):
        called.append("labels")
        return [], labels_api.API

    monkeypatch.setattr(post, "process_labels", fake_labels)
    monkeypatch.setattr(post.log, "info", lambda msg, *a, **k: infos.append(str(msg)))
    monkeypatch.setattr(post, "get_final_posts_area", lambda: {"Labels"})
    monkeypatch.setattr(post, "get_like_area", lambda: set())
    monkeypatch.setattr(post, "get_download_area", lambda: {"Labels"})
    monkeypatch.setattr(post.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    fansly.skip_unavailable_content = False
    asyncio.run(post.process_tasks(CREATOR_ID, CREATOR, SimpleNamespace(active=False)))
    assert called == []
    assert any("Skipping labels" in m and CREATOR in m for m in infos)


def test_labels_only_run_downloads_the_wall_posts(fansly, tmp_db, monkeypatch):
    fansly.command = "download"
    fansly.text = False
    c = FakeSession(make_route())
    collection = run_areas(monkeypatch, ["Labels"], c)
    assert sorted(p.id for p in collection.posts) == sorted(ALL_POSTS)
    assert all(p.is_download_candidate for p in collection.posts)
    # the plain timeline (no wallId) was not fetched
    assert "" not in wall_calls(c)
