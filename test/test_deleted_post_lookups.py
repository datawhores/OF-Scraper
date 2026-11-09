"""Posts a scan marked deleted are left out of the archived and streams lookups.

The lookups feed the scan's starting point: the oldest post they return is
where the first archived or streams page request starts (issue #318).
"""

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
