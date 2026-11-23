"""Deleted models, profile info after failure, paid usernames, and deleted post lookups."""

# ----------------------------------------------------------------------
# From test_profile_deleted_model.py
# ----------------------------------------------------------------------

import asyncio
from types import SimpleNamespace

import ofscraper.data.posts.post as post
import ofscraper.utils.of_env.of_env as of_env


def _process(monkeypatch, scraped):
    monkeypatch.setattr(post.profile, "scrape_profile", lambda username: scraped)
    monkeypatch.setattr(
        post.free.settings, "get_settings", lambda: SimpleNamespace(system_free_min=0)
    )
    tracebacks = []
    monkeypatch.setattr(post.log, "traceback_", tracebacks.append, raising=False)
    result = asyncio.run(post.process_profile("gone"))
    return result, tracebacks


def test_deleted_model_profile_is_skipped_without_error(monkeypatch):
    placeholder = {"username": of_env.getattr("DELETED_MODEL_PLACEHOLDER")}
    result, tracebacks = _process(monkeypatch, placeholder)
    assert result == ([], post.profile.API)
    assert tracebacks == []


def test_existing_profile_still_yields_its_media(monkeypatch):
    scraped = {
        "id": 1,
        "username": "model",
        "name": "Model",
        "avatar": "https://example.invalid/avatar.jpg",
        "joinDate": "2020-01-01T00:00:00+00:00",
        "postsCount": 0,
        "photosCount": 0,
        "videosCount": 0,
        "audiosCount": 0,
        "archivedPostsCount": 0,
    }
    (posts, api), tracebacks = _process(monkeypatch, scraped)
    assert api == post.profile.API and tracebacks == []
    assert len(posts) == 1 and posts[0].model_id == 1

# ----------------------------------------------------------------------
# From test_profile_info_after_failure.py
# ----------------------------------------------------------------------

import httpx
import pytest

import ofscraper.data.api.me as me
import ofscraper.utils.profiles.data as profile_data


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.setattr(profile_data, "currentProfile", None)
    monkeypatch.setattr(profile_data, "currentData", None)
    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")


def test_failed_scrape_is_retried_on_the_next_call(profile, monkeypatch):
    def offline():
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(me, "scrape_user", offline)
    with pytest.raises(httpx.ConnectTimeout):
        profile_data.get_my_info()

    user = {"isAuth": True, "id": 1, "username": "u1", "name": "n1"}
    monkeypatch.setattr(me, "scrape_user", lambda: user)
    assert profile_data.get_my_info() == user


def test_successful_scrape_is_reused(profile, monkeypatch):
    calls = []

    def scrape_user():
        calls.append(1)
        return {"isAuth": True, "id": 1, "username": "u1", "name": "n1"}

    monkeypatch.setattr(me, "scrape_user", scrape_user)
    profile_data.get_my_info()
    profile_data.get_my_info()
    assert len(calls) == 1

# ----------------------------------------------------------------------
# From test_resolve_paid_username.py
# resolve_paid_username: the paid-content creator name, public so the GUI can reuse it.
# ----------------------------------------------------------------------

import asyncio

import pytest

import ofscraper.data.posts.post as post

PLACEHOLDER = "modeldeleted"


@pytest.fixture
def lookups(monkeypatch):
    """Stub the profile and DB lookups; returns (configure, db_calls)."""
    db_calls = []
    state = {}

    async def table_exists(model_id=None, username=None):
        db_calls.append(("exists", model_id, username))
        return state["in_db"]

    async def profile_info(model_id=None, username=None):
        db_calls.append(("info", model_id, username))
        return state["recorded"]

    monkeypatch.setenv("OFSC_DELETED_MODEL_PLACEHOLDER", PLACEHOLDER)
    monkeypatch.setattr(
        post.profile, "scrape_profile", lambda model_id: {"username": state["scraped"]}
    )
    monkeypatch.setattr(post, "check_profile_table_exists", table_exists)
    monkeypatch.setattr(post, "get_profile_info", profile_info)

    def configure(scraped, in_db=None, recorded=None):
        state.update(scraped=scraped, in_db=in_db, recorded=recorded)

    return configure, db_calls


@pytest.mark.parametrize(
    "scraped, in_db, recorded, expected",
    [
        # a live creator: the scraped name, no DB lookup
        ("creator_a", None, None, "creator_a"),
        # deleted, and an earlier run recorded its name
        (PLACEHOLDER, True, "old_name", "old_name"),
        # deleted, in the DB but no name stored
        (PLACEHOLDER, True, None, f"{PLACEHOLDER}_7"),
        # deleted and never seen before
        (PLACEHOLDER, False, None, f"{PLACEHOLDER}_7"),
    ],
)
def test_resolve_paid_username(lookups, scraped, in_db, recorded, expected):
    configure, db_calls = lookups
    configure(scraped, in_db, recorded)

    assert asyncio.run(post.resolve_paid_username(7)) == expected
    if scraped != PLACEHOLDER:
        assert db_calls == []
    elif in_db:
        assert db_calls == [
            ("exists", 7, PLACEHOLDER),
            ("info", 7, PLACEHOLDER),
        ]
    else:
        assert db_calls == [("exists", 7, PLACEHOLDER)]

# ----------------------------------------------------------------------
# From test_deleted_post_lookups.py
# Posts a scan marked deleted are left out of the archived and streams lookups.
#
# The lookups feed the scan's starting point: the oldest post they return is
# where the first archived or streams page request starts (issue #318).
# ----------------------------------------------------------------------

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.api.archive as archive
import ofscraper.data.api.streams as streams
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.posts import (
    get_archived_post_info,
    get_streams_post_info,
    mark_post_as_deleted,
)

MODEL_ID = 12345
USERNAME = "lookupmodel"
AFTER = 946684800.0  # 2000-01-01, the default scan start with no history

DELETED_ID = 1
KEPT_ID = 2
NULL_ID = 3
# a deleted post older than the kept ones, so it would set the scan start
DATES = {
    DELETED_ID: "2024-01-01T10:00:00.250000+00:00",
    KEPT_ID: "2024-03-01T10:00:00.250000+00:00",
    NULL_ID: "2024-05-01T10:00:00.250000+00:00",
}


def api_post(post_id, kind):
    post = {
        "id": post_id,
        "text": "text",
        "price": 0,
        "isOpened": True,
        "postedAt": DATES[post_id],
        "responseType": "post",
        "media": [],
    }
    if kind == "archived":
        post["isArchived"] = True
    else:
        post["streamId"] = 900 + post_id
    return post


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)

    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(api_cached_disabled=False, metadata=None)
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return db


def seed(db, kind):
    async def write():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        rows = [
            posts_.Post(api_post(post_id, kind), MODEL_ID, USERNAME)
            for post_id in DATES
        ]
        await operations.make_post_table_changes(
            rows, model_id=MODEL_ID, username=USERNAME
        )
        await mark_post_as_deleted(
            [DELETED_ID], model_id=MODEL_ID, username=USERNAME
        )

    asyncio.run(write())
    # a row from before the is_deleted column had a value
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute("UPDATE posts SET is_deleted = NULL WHERE post_id = ?", [NULL_ID])
        conn.commit()
        flags = dict(conn.execute("SELECT post_id, is_deleted FROM posts").fetchall())
    assert flags == {DELETED_ID: 1, KEPT_ID: 0, NULL_ID: None}


LOOKUPS = {"archived": get_archived_post_info, "streams": get_streams_post_info}


@pytest.mark.parametrize("kind", ["archived", "streams"])
def test_lookup_skips_deleted_posts(tmp_db, kind):
    seed(tmp_db, kind)
    found = asyncio.run(LOOKUPS[kind](model_id=MODEL_ID, username=USERNAME))
    assert sorted(row["post_id"] for row in found) == [KEPT_ID, NULL_ID]


def record_scrape(c, model_id, username, timestamp=None, required_posts=None, **kwargs):
    return {
        "timestamp": timestamp,
        "post_ids": [p["post_id"] for p in required_posts or []],
    }


@pytest.mark.parametrize(
    "module,scrape",
    [(archive, "scrape_archived_posts"), (streams, "scrape_stream_posts")],
    ids=["archived", "streams"],
)
def test_scan_starts_from_oldest_post_not_deleted(tmp_db, monkeypatch, module, scrape):
    seed(tmp_db, "archived" if module is archive else "streams")
    monkeypatch.setattr(module, scrape, record_scrape)

    split = asyncio.run(module.get_split_array(MODEL_ID, USERNAME, AFTER))
    tasks = module.get_tasks(split, None, MODEL_ID, USERNAME, AFTER)

    kept = arrow.get(DATES[KEPT_ID]).float_timestamp
    # the gap worker sweeps from `after` up to the oldest known post
    assert tasks[0] == {"timestamp": AFTER, "post_ids": [KEPT_ID]}
    # and the first known chunk starts at that post, not at the deleted one
    assert tasks[1]["timestamp"] == kept
    assert all(DELETED_ID not in task["post_ids"] for task in tasks)
