"""The metadata command locks stray items without crashing (#376).

A stray item is one in the database that the current scrape no longer sees.
With --mark-stray-locked the metadata command locks them (unlocked = 0). It
used to `await` the sync database call that does this, so the update ran and
then `await None` raised a TypeError.

Each test builds a real SQLite database in a temporary folder with the app's
own create and upgrade code, and runs the command's own stray step on it.
"""

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.commands.metadata.metadata as metadata
import ofscraper.db.operations as operations
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.transition as transition
from ofscraper.db.operations_.profile import write_models_table, write_profile_table

MODEL_ID = 37600
USERNAME = "straymodel"


def call(func, *args, **kwargs):
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


def rows(db, sql, *args):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return conn.execute(sql, args).fetchall()


def insert_media(db, media_id, downloaded=0, unlocked=1):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " downloaded, unlocked, posted_at, model_id)"
            " VALUES (?, ?, 'Timeline', 'Images', ?, ?, ?, ?)",
            [media_id, 9000 + media_id, downloaded, unlocked, "2024-01-01", MODEL_ID],
        )
        conn.commit()


def unlocked(db):
    return dict(rows(db, "SELECT media_id, unlocked FROM medias ORDER BY media_id"))


@pytest.fixture
def db(tmp_path, monkeypatch):
    db = tmp_path / "user_data.db"
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)

    # the stray step finds the database by creator, like a real run
    class Placeholder:
        def databasePathHelper(self, model_id, username):
            return db

    monkeypatch.setattr(wrapper.placeholder, "databasePlaceholder", Placeholder)
    monkeypatch.setattr(
        metadata.settings,
        "get_settings",
        lambda: SimpleNamespace(mark_stray=True),
    )
    monkeypatch.setattr(
        metadata.settings,
        "get_args",
        lambda: SimpleNamespace(
            download_area=["Timeline"], after=None, before=arrow.now()
        ),
    )
    monkeypatch.setattr(
        metadata.progress_updater.activity, "update_task", lambda **_: None
    )
    return db


def run_stray_step(scraped_ids):
    manager = metadata.MetadataCommandManager()
    scraped = [SimpleNamespace(id=media_id) for media_id in scraped_ids]
    asyncio.run(manager._metadata_stray_media(USERNAME, MODEL_ID, scraped))


def test_stray_items_are_locked_without_error(db):
    insert_media(db, 1)  # still in the scrape
    insert_media(db, 2)  # stray
    insert_media(db, 3)  # stray
    insert_media(db, 4, downloaded=1)  # stray, but already downloaded
    run_stray_step([1])
    assert unlocked(db) == {1: 1, 2: 0, 3: 0, 4: 1}


def test_no_stray_items_changes_nothing(db):
    insert_media(db, 1)
    insert_media(db, 2)
    run_stray_step([1, 2])
    assert unlocked(db) == {1: 1, 2: 1}
