"""A post or message flagged deleted that the API returns again is no longer
deleted (#323).

Each test builds a real SQLite database in a temporary folder and writes posts
and messages through the app's own scan path (make_post_table_changes,
make_messages_table_changes and the mark_*_as_deleted calls).
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
import ofscraper.data.api.labels as labels
import ofscraper.data.api.messages as messages_api
import ofscraper.data.api.streams as streams
import ofscraper.data.api.timeline as timeline
import ofscraper.db.operations as operations
import ofscraper.db.operations_.messages as messages
import ofscraper.db.operations_.posts as posts
import ofscraper.utils.settings as settings

MODEL_ID = 12345
USERNAME = "dbmodel"
RETURNING = 2001
OTHER = 2002
OLD_DATE = "2024-03-01T10:00:00+00:00"
NEW_DATE = "2024-09-01T10:00:00+00:00"

# responsetype, the fields that put a post in that area, the media api_type,
# and the area's get_after
AREAS = {
    "timeline": ("Timeline", {}, "Timeline", timeline),
    "archived": ("Archived", {"isArchived": True}, "Archived", archive),
    "streams": ("Streams", {"streamId": 77}, "Streams", streams),
}


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


def run_settings(monkeypatch, metadata):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(metadata=metadata, mediatypes=["Images"])
    monkeypatch.setattr(settings, "get_settings", lambda: stub)


@pytest.fixture
def normal_run(monkeypatch):
    run_settings(monkeypatch, None)


@pytest.fixture
def metadata_run(monkeypatch):
    run_settings(monkeypatch, "check")


def post(area, post_id, text, date, price=0, opened=False):
    responsetype, fields, _, _ = AREAS[area]
    item = {
        "id": post_id,
        "text": text,
        "price": price,
        "postedAt": date,
        "isOpened": opened,
        "media": [],
        **fields,
    }
    return posts_.Post(item, MODEL_ID, USERNAME, responsetype)


def dump(db, table="posts"):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        return {
            row["post_id"]: dict(row)
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY post_id")
        }


def scan(*items):
    # as the scan areas call it: everything came from the API in this run
    return posts.make_post_table_changes(
        list(items), model_id=MODEL_ID, username=USERNAME, from_api=True
    )


async def deleted_after_first_scan(area):
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await scan(post(area, RETURNING, "first text", OLD_DATE))
    await posts.mark_post_as_deleted(
        [RETURNING], model_id=MODEL_ID, username=USERNAME
    )
    assert await posts.get_deleted_post_ids(model_id=MODEL_ID, username=USERNAME) == {
        RETURNING
    }


@pytest.mark.parametrize("area", AREAS)
def test_normal_scan_clears_only_the_deleted_flag(tmp_db, normal_run, area):
    async def run():
        await deleted_after_first_scan(area)
        before = dump(tmp_db)
        # the API now returns the post with different details; without
        # --metadata none of them may be written
        await scan(post(area, RETURNING, "edited text", NEW_DATE, price=5, opened=True))
        deleted = await posts.get_deleted_post_ids(
            model_id=MODEL_ID, username=USERNAME
        )
        return before, deleted

    before, deleted = asyncio.run(run())
    assert deleted == set()
    after = dump(tmp_db)
    assert before[RETURNING]["is_deleted"] == 1
    assert after[RETURNING] == dict(before[RETURNING], is_deleted=0)


@pytest.mark.parametrize("area", AREAS)
def test_metadata_scan_clears_the_flag_and_updates_as_before(
    tmp_db, metadata_run, area
):
    async def run():
        await deleted_after_first_scan(area)
        before = dump(tmp_db)
        await scan(post(area, RETURNING, "edited text", NEW_DATE, price=5))
        return before

    before = asyncio.run(run())
    after = dump(tmp_db)[RETURNING]
    assert after == dict(
        before[RETURNING],
        is_deleted=0,
        text="edited text",
        price=5,
        paid=1,
        created_at=NEW_DATE,
    )


def test_normal_scan_leaves_other_posts_alone(tmp_db, normal_run):
    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        await scan(
            post("timeline", RETURNING, "first text", OLD_DATE),
            post("timeline", OTHER, "other text", OLD_DATE),
        )
        await posts.mark_post_as_deleted(
            [RETURNING, OTHER], model_id=MODEL_ID, username=USERNAME
        )
        await scan(post("timeline", RETURNING, "first text", OLD_DATE))
        return await posts.get_deleted_post_ids(model_id=MODEL_ID, username=USERNAME)

    # only the post the API returned comes back
    assert asyncio.run(run()) == {OTHER}


def insert_media(db, rows):
    cols = [
        "media_id", "post_id", "link", "api_type", "media_type", "preview",
        "linked", "downloaded", "created_at", "posted_at", "model_id", "unlocked",
    ]
    marks = ",".join("?" for _ in cols)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            f"INSERT INTO medias ({','.join(cols)}) VALUES ({marks})", rows
        )
        conn.commit()


def media_row(api_type, media_id, post_id, downloaded, date):
    return (
        media_id, post_id, f"https://example.invalid/{media_id}.jpg", api_type,
        "Images", 0, None, downloaded, date, date, MODEL_ID, 1,
    )


@pytest.mark.parametrize("area", AREAS)
def test_returning_post_counts_for_the_next_scan_start(
    tmp_db, normal_run, monkeypatch, area
):
    _, _, api_type, module = AREAS[area]
    monkeypatch.setattr(module, "get_after_pre_checks", lambda *a, **k: None)

    async def run():
        await deleted_after_first_scan(area)
        await scan(post(area, OTHER, "newer post", NEW_DATE))
        # the returning post has media still to download; the newer one doesn't
        insert_media(
            tmp_db,
            [
                media_row(api_type, 3001, RETURNING, 0, OLD_DATE),
                media_row(api_type, 3002, OTHER, 1, NEW_DATE),
            ],
        )
        await scan(post(area, RETURNING, "first text", OLD_DATE))
        after = await module.get_after(MODEL_ID, USERNAME)
        missing = await labels.get_posts_missing_media(MODEL_ID, USERNAME)
        return after, missing

    after, missing = asyncio.run(run())
    # the next scan starts back at the returning post's undownloaded media
    assert after == arrow.get(OLD_DATE).float_timestamp
    assert missing == {str(RETURNING)}


def message(post_id, text, date, price=0):
    item = {
        "id": post_id,
        "text": text,
        "price": price,
        "createdAt": date,
        "fromUser": {"id": MODEL_ID},
        "media": [],
    }
    return posts_.Post(item, MODEL_ID, USERNAME, "Messages")


def scan_messages(*items):
    return messages.make_messages_table_changes(
        list(items), model_id=MODEL_ID, username=USERNAME, from_api=True
    )


def deleted_messages():
    return messages.get_deleted_messages_ids(model_id=MODEL_ID, username=USERNAME)


async def message_deleted_after_first_scan():
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await scan_messages(message(RETURNING, "first text", OLD_DATE))
    await messages.mark_message_as_deleted(
        [RETURNING], model_id=MODEL_ID, username=USERNAME
    )
    assert await deleted_messages() == {RETURNING}


def test_normal_scan_clears_only_a_messages_deleted_flag(tmp_db, normal_run):
    async def run():
        await message_deleted_after_first_scan()
        before = dump(tmp_db, "messages")
        await scan_messages(message(RETURNING, "edited text", NEW_DATE, price=5))
        return before, await deleted_messages()

    before, deleted = asyncio.run(run())
    assert deleted == set()
    assert before[RETURNING]["is_deleted"] == 1
    after = dump(tmp_db, "messages")
    assert after[RETURNING] == dict(before[RETURNING], is_deleted=0)


def test_metadata_scan_clears_a_messages_flag_and_updates_as_before(
    tmp_db, metadata_run
):
    async def run():
        await message_deleted_after_first_scan()
        before = dump(tmp_db, "messages")
        await scan_messages(message(RETURNING, "edited text", NEW_DATE, price=5))
        return before

    before = asyncio.run(run())
    after = dump(tmp_db, "messages")[RETURNING]
    assert after == dict(
        before[RETURNING],
        is_deleted=0,
        text="edited text",
        price=5,
        paid=1,
        created_at=NEW_DATE,
    )


def test_normal_scan_leaves_other_messages_alone(tmp_db, normal_run):
    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        await scan_messages(
            message(RETURNING, "first text", OLD_DATE),
            message(OTHER, "other text", OLD_DATE),
        )
        await messages.mark_message_as_deleted(
            [RETURNING, OTHER], model_id=MODEL_ID, username=USERNAME
        )
        await scan_messages(message(RETURNING, "first text", OLD_DATE))
        return await deleted_messages()

    # only the message the API returned comes back
    assert asyncio.run(run()) == {OTHER}


def test_returning_message_counts_for_the_next_scan_start(
    tmp_db, normal_run, monkeypatch
):
    monkeypatch.setattr(messages_api, "get_after_pre_checks", lambda *a, **k: None)

    async def run():
        await message_deleted_after_first_scan()
        await scan_messages(message(OTHER, "newer message", NEW_DATE))
        # the returning message has media still to download; the newer one doesn't
        insert_media(
            tmp_db,
            [
                media_row("Messages", 3001, RETURNING, 0, OLD_DATE),
                media_row("Messages", 3002, OTHER, 1, NEW_DATE),
            ],
        )
        await scan_messages(message(RETURNING, "first text", OLD_DATE))
        return await messages_api.get_after(MODEL_ID, USERNAME)

    # the next scan starts back at the returning message's undownloaded media
    assert asyncio.run(run()) == arrow.get(OLD_DATE).float_timestamp
