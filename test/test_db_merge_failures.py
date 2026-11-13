"""Merge DB's finishes and reports a database that fails to merge (#300).

Each test builds real SQLite databases in a temporary folder with the app's
own create, migration and write code, next to a source that isn't a database.
"""

import asyncio
import contextlib
import sqlite3

import pytest

import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.utils.merge as merge_menu
from ofscraper.db.operations_.posts import write_post_table_transition
from ofscraper.db.operations_.profile import write_models_table, write_profile_table
from ofscraper.db.transition import modify_tables

MODEL_ID = 12345
USERNAME = "dbmodel"
POST = {
    "post_id": 1001,
    "text": "post one",
    "price": 0,
    "paid": 0,
    "archived": 0,
    "pinned": 0,
    "stream": 0,
    "opened": 1,
    "created_at": "2024-01-03T03:04:05+00:00",
    "model_id": MODEL_ID,
    "is_deleted": 0,
}


async def make_db(db):
    db.parent.mkdir(parents=True, exist_ok=True)
    await operations.create_tables(db_path=db)
    await write_profile_table(model_id=MODEL_ID, username=USERNAME, db_path=db)
    await write_models_table(model_id=MODEL_ID, db_path=db)
    await modify_tables(db_path=db)
    await write_post_table_transition([POST], db_path=db)


def post_ids(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return [row[0] for row in conn.execute("SELECT post_id FROM posts")]


@pytest.fixture
def sources(tmp_path, monkeypatch):
    """A folder with a corrupt source first, then a good one, and the log."""
    old = tmp_path / "old"
    bad = old / "bad" / "user_data.db"
    good = old / "good" / "user_data.db"
    new_db = tmp_path / "new" / "user_data.db"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"this is not a sqlite database" * 100)
    asyncio.run(make_db(good))
    # the merge reads databases in folder-walk order; fix the order here
    monkeypatch.setattr(merge.paths_db, "get_all_db", lambda folder: [bad, good])
    logged = []
    monkeypatch.setattr(merge.log, "info", lambda msg, *a, **k: logged.append(msg))
    monkeypatch.setattr(merge.log, "traceback_", lambda *a, **k: None, raising=False)
    return old, bad, new_db, logged


def test_failed_source_is_reported_and_the_rest_merged(sources):
    old, bad, new_db, logged = sources

    failures, success, empty = asyncio.run(merge.MergeDatabase()(old, new_db))

    assert [path for path, _ in failures] == [bad]
    failure = failures[0][1]
    assert failure["path"] == str(bad)
    assert isinstance(failure["reason"], sqlite3.DatabaseError)
    assert [model for model, _ in success] == [MODEL_ID]
    assert empty == []
    assert post_ids(new_db) == [POST["post_id"]]
    # the last log line lists the failed database and why
    assert repr(str(bad)) in logged[-1]
    assert repr(failure["reason"]) in logged[-1]


def test_menu_merge_returns_the_summary_with_a_failure(sources):
    old, bad, new_db, _ = sources
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        completed, skipped, failed = merge_menu.merge_loop(old, new_db)
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    assert [model for model, _ in completed] == [MODEL_ID]
    assert skipped == []
    assert [path for path, _ in failed] == [bad]
