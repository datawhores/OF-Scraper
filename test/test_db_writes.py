"""Database writes for stories, products, others and messages (#203).

Each test builds a real SQLite database in a temporary folder with the app's
own create and migration code.
"""

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.operations_.others as others
import ofscraper.db.utils.rebuild as rebuild
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.messages import (
    get_deleted_messages_ids,
    mark_message_as_deleted,
)
from ofscraper.db.operations_.profile import write_models_table, write_profile_table
from ofscraper.db.transition import modify_tables

MODEL_ID = 12345
USERNAME = "dbmodel"

PRODUCT_COLS = ["post_id", "text", "price", "paid", "archived", "created_at", "title", "model_id"]
OTHER_COLS = ["post_id", "text", "price", "paid", "archived", "created_at", "model_id"]
MESSAGE_COLS = [
    "post_id", "text", "price", "paid", "archived", "created_at", "user_id", "model_id",
    "is_deleted",
]

PRODUCTS = [
    (501, "product one", 10, 1, 0, "2024-01-02T03:04:05+00:00", "first title", MODEL_ID),
    (502, "product two", 0, 0, 1, "2024-02-02T03:04:05+00:00", "second title", MODEL_ID),
]
OTHERS = [
    (601, "other one", 3, 1, 0, "2024-03-02T03:04:05+00:00", MODEL_ID),
    (602, "other two", 0, 0, 1, "2024-04-02T03:04:05+00:00", MODEL_ID),
]
MESSAGES = [
    (701, "kept message", 5, 1, 0, "2024-05-02T03:04:05+00:00", MODEL_ID, MODEL_ID, 0),
    (702, "deleted message", 0, 0, 0, "2024-06-02T03:04:05+00:00", MODEL_ID, MODEL_ID, 1),
]


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    return db


@pytest.fixture
def metadata_run(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(metadata="check")
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return stub


def rows(db, table, cols):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(conn.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall())


def insert(db, table, cols, data):
    marks = ",".join("?" for _ in cols)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({marks})", data)
        conn.commit()


def without_model_id(cols, data):
    # rows written before the model_id column existed have it empty
    at = cols.index("model_id")
    return [row[:at] + (None,) + row[at + 1 :] for row in data]


async def new_database(db):
    """A database as an old version left it: tables and rows, no schema flags yet."""
    await operations.create_tables(db_path=db)
    await write_profile_table(model_id=MODEL_ID, username=USERNAME, db_path=db)
    await write_models_table(model_id=MODEL_ID, db_path=db)


def story(text):
    item = {
        "id": 801,
        "text": text,
        "price": 0,
        "createdAt": "2024-07-01T10:00:00+00:00",
        "media": [],
    }
    return posts_.Post(item, MODEL_ID, USERNAME, "Stories")


def message(text):
    item = {
        "id": 901,
        "text": text,
        "price": 0,
        "createdAt": "2024-08-01T10:00:00+00:00",
        "fromUser": {"id": MODEL_ID},
        "media": [],
    }
    return posts_.Post(item, MODEL_ID, USERNAME, "Messages")


def test_metadata_run_updates_an_existing_story(tmp_db, metadata_run):
    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        await operations.make_stories_table_changes(
            [story("old text")], model_id=MODEL_ID, username=USERNAME
        )
        await operations.make_stories_table_changes(
            [story("new text")], model_id=MODEL_ID, username=USERNAME
        )

    asyncio.run(run())
    assert rows(tmp_db, "stories", ["post_id", "text"]) == [(801, "new text")]


def test_metadata_run_updates_messages_passed_as_an_iterator(tmp_db, metadata_run):
    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        await operations.make_changes_to_content_tables(
            [message("old text")], model_id=MODEL_ID, username=USERNAME
        )
        await operations.make_changes_to_content_tables(
            [message("new text")], model_id=MODEL_ID, username=USERNAME
        )

    asyncio.run(run())
    assert rows(tmp_db, "messages", ["post_id", "text"]) == [(901, "new text")]


def test_message_seen_again_is_no_longer_flagged_deleted(tmp_db, metadata_run):
    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        await operations.make_messages_table_changes(
            [message("text")], model_id=MODEL_ID, username=USERNAME
        )
        await mark_message_as_deleted([901], model_id=MODEL_ID, username=USERNAME)
        assert await get_deleted_messages_ids(model_id=MODEL_ID, username=USERNAME) == {901}
        await operations.make_messages_table_changes(
            [message("text")], model_id=MODEL_ID, username=USERNAME
        )
        return await get_deleted_messages_ids(model_id=MODEL_ID, username=USERNAME)

    assert asyncio.run(run()) == set()
    assert rows(tmp_db, "messages", ["post_id", "is_deleted"]) == [(901, 0)]


def test_model_id_rebuild_keeps_every_row_and_column(tmp_path):
    db = tmp_path / "user_data.db"

    async def run():
        await new_database(db)
        insert(db, "products", PRODUCT_COLS, without_model_id(PRODUCT_COLS, PRODUCTS))
        insert(db, "others", OTHER_COLS, without_model_id(OTHER_COLS, OTHERS))
        insert(db, "messages", MESSAGE_COLS, without_model_id(MESSAGE_COLS, MESSAGES))
        await modify_tables(db_path=db)

    asyncio.run(run())
    assert rows(db, "products", PRODUCT_COLS) == PRODUCTS
    assert rows(db, "others", OTHER_COLS) == OTHERS
    assert rows(db, "messages", MESSAGE_COLS) == MESSAGES


def test_failed_rebuild_leaves_the_old_table_untouched(tmp_path, monkeypatch):
    db = tmp_path / "user_data.db"

    async def duplicate_rows(**kwargs):
        # two rows with the same (post_id, model_id) break the new table's unique key
        return [dict(zip(OTHER_COLS, OTHERS[0]))] * 2

    async def run():
        await new_database(db)
        insert(db, "others", OTHER_COLS, OTHERS)
        monkeypatch.setattr(others, "get_all_others_transition", duplicate_rows)
        with pytest.raises(sqlite3.IntegrityError):
            await others.rebuild_others_table(db_path=db)

    asyncio.run(run())
    assert rows(db, "others", OTHER_COLS) == OTHERS


def tables(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )


def test_failed_rebuild_on_a_plain_connection_leaves_no_trace(tmp_path):
    db = tmp_path / "user_data.db"
    asyncio.run(new_database(db))
    insert(db, "others", OTHER_COLS, OTHERS)
    before = tables(db)
    duplicate = [OTHERS[0], OTHERS[0]]
    with contextlib.closing(sqlite3.connect(db)) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            rebuild.replace_table(
                conn, "others", others.otherCreate, others.othersInsert, duplicate
            )
    assert tables(db) == before
    assert rows(db, "others", OTHER_COLS) == OTHERS


def test_rebuild_keeps_views_on_the_table_working(tmp_path):
    db = tmp_path / "user_data.db"

    async def run():
        await new_database(db)
        insert(db, "others", OTHER_COLS, without_model_id(OTHER_COLS, OTHERS))
        with contextlib.closing(sqlite3.connect(db)) as conn:
            conn.execute("CREATE VIEW others_view AS SELECT post_id FROM others")
            conn.commit()
        await others.rebuild_others_table(db_path=db)

    asyncio.run(run())
    assert rows(db, "others", OTHER_COLS) == OTHERS
    assert rows(db, "others_view", ["post_id"]) == [(601,), (602,)]
    assert "others_rebuild_new" not in tables(db)


def test_merge_copies_products_others_and_messages(tmp_path, monkeypatch):
    old_db = tmp_path / "old" / "creator" / "user_data.db"
    new_db = tmp_path / "new" / "user_data.db"
    old_db.parent.mkdir(parents=True)

    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    monkeypatch.setattr(merge.log, "traceback_", fail, raising=False)

    async def run():
        await new_database(old_db)
        await modify_tables(db_path=old_db)
        insert(old_db, "products", PRODUCT_COLS, PRODUCTS)
        insert(old_db, "others", OTHER_COLS, OTHERS)
        insert(old_db, "messages", MESSAGE_COLS, MESSAGES)
        return await merge.MergeDatabase()(tmp_path / "old", new_db)

    failures, success, empty = asyncio.run(run())
    assert failures == []
    assert [model for model, _ in success] == [MODEL_ID]
    assert rows(new_db, "products", PRODUCT_COLS) == PRODUCTS
    assert rows(new_db, "others", OTHER_COLS) == OTHERS
    assert rows(new_db, "messages", MESSAGE_COLS) == MESSAGES
