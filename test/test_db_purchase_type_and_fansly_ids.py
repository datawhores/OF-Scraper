"""The purchase type, Fansly conversation id and Fansly mentions are saved (#315).

``posts.purchase_type`` records whether an OnlyFans purchase was a post or a
message, ``messages.group_id`` the Fansly conversation of a message, and
``posts.mentions`` a Fansly post's ``accountMentions`` list. All three are
optional: older databases gain them empty and later scans fill them in.

Each test builds a real SQLite database in a temporary folder and writes it
through the app's own scrape, upgrade, rebuild and merge code. The Fansly
data comes from the anonymised fixtures in ``test/fixtures/fansly``.
"""

import asyncio
import contextlib
import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.posts.post as post
import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.transition as transition
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.settings as settings
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.profile import write_models_table, write_profile_table

from test_fansly_api import (
    CREATOR_ID,
    DM_CREATOR,
    DM_CREATOR_ID,
    GROUP_ID,
    FakeSession,
    load,
    messages_route,
    timeline_route,
)

MODEL_ID = 31500
USERNAME = "purchasemodel"
NEW_FLAGS = ("posts_purchase_type", "posts_mentions", "messages_group_id")

BOUGHT_POST = {
    "id": 5001,
    "text": "bought post",
    "price": 3,
    "isOpened": True,
    "postedAt": "2024-07-01T10:00:00+00:00",
    "responseType": "post",
    "media": [],
}
BOUGHT_MESSAGE = {
    "id": 5002,
    "text": "bought message",
    "price": 4,
    "isOpened": True,
    "createdAt": "2024-07-02T10:00:00+00:00",
    "responseType": "message",
    "fromUser": {"id": MODEL_ID},
    "media": [],
}

# The fixtures only hold empty accountMentions lists. This entry is made up:
# the app stores the list exactly as sent and doesn't read its fields.
MENTIONED_POST = 100000000000000001
MENTIONS = [{"accountId": "100000000000000900", "handle": "samplefriend1"}]


@pytest.fixture
def model_db(monkeypatch, tmp_path):
    db = tmp_path / "data" / "user_data.db"
    db.parent.mkdir()
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    # only the backup taken before an upgrade is under test
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    store = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value, **k: store.update({key: value}))
    monkeypatch.setattr(post, "set_after_checks", lambda *a, **k: None)

    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    # surface errors the area functions would otherwise only log
    monkeypatch.setattr(post.log, "traceback_", fail, raising=False)
    return db


def use_site(monkeypatch, site, metadata=None):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(
        site=site, after=None, post_id=None, timeline_strict=False, usernames=None,
        metadata=metadata,
    )
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return stub


@pytest.fixture
def onlyfans(monkeypatch, model_db):
    return use_site(monkeypatch, "onlyfans")


@pytest.fixture
def fansly(monkeypatch, model_db):
    return use_site(monkeypatch, "fansly")


def fetcher(items):
    async def fetch(*args, **kwargs):
        return copy.deepcopy(items)

    return fetch


def call(func, *args, **kwargs):
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


def rows(db, sql, *args):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return conn.execute(sql, args).fetchall()


def columns(db, table):
    return [r[1] for r in rows(db, f"PRAGMA table_info({table})")]


async def scrape_paid(model_id=MODEL_ID, username=USERNAME):
    await operations.table_init_create(model_id=model_id, username=username)
    await post.process_paid_post(model_id, username, None)


async def scrape_timeline(model_id=MODEL_ID, username=USERNAME, c=None):
    await operations.table_init_create(model_id=model_id, username=username)
    await post.process_timeline_posts(model_id, username, c)


async def scrape_messages(model_id=MODEL_ID, username=USERNAME, c=None):
    await operations.table_init_create(model_id=model_id, username=username)
    await post.process_messages(model_id, username, c)


def purchase_types(db):
    return rows(db, "SELECT post_id, purchase_type FROM posts ORDER BY post_id")


# ------------------------------------------------------------------ purchase type


def test_onlyfans_purchase_records_post_or_message(onlyfans, model_db, monkeypatch):
    monkeypatch.setattr(post.paid, "get_paid_posts", fetcher([BOUGHT_POST, BOUGHT_MESSAGE]))

    asyncio.run(scrape_paid())

    assert purchase_types(model_db) == [(5001, "post"), (5002, "message")]


@pytest.mark.parametrize("metadata", [None, "check"])
def test_timeline_scan_keeps_the_purchase_type(monkeypatch, model_db, metadata):
    use_site(monkeypatch, "onlyfans", metadata=metadata)
    monkeypatch.setattr(post.paid, "get_paid_posts", fetcher([BOUGHT_POST]))
    monkeypatch.setattr(post.timeline, "get_timeline_posts", fetcher([BOUGHT_POST]))

    asyncio.run(scrape_paid())
    asyncio.run(scrape_timeline())

    assert purchase_types(model_db) == [(5001, "post")]


def test_purchase_scan_fills_in_a_post_saved_from_the_timeline(onlyfans, model_db, monkeypatch):
    monkeypatch.setattr(post.timeline, "get_timeline_posts", fetcher([BOUGHT_POST]))
    monkeypatch.setattr(post.paid, "get_paid_posts", fetcher([BOUGHT_POST]))

    asyncio.run(scrape_timeline())
    assert purchase_types(model_db) == [(5001, None)]
    asyncio.run(scrape_paid())

    assert purchase_types(model_db) == [(5001, "post")]


def test_timeline_post_has_no_purchase_type(onlyfans, model_db, monkeypatch):
    monkeypatch.setattr(post.timeline, "get_timeline_posts", fetcher([BOUGHT_POST]))

    asyncio.run(scrape_timeline())

    assert rows(model_db, "SELECT purchase_type, mentions FROM posts") == [(None, None)]


# ------------------------------------------------------------------ Fansly ids


def test_fansly_message_records_its_conversation(fansly, model_db):
    c = FakeSession(messages_route)

    asyncio.run(scrape_messages(DM_CREATOR_ID, DM_CREATOR, c))

    raw = load("messages.json")["response"]["messages"]
    assert rows(model_db, "SELECT post_id, group_id FROM messages ORDER BY post_id") == sorted(
        (int(m["id"]), GROUP_ID) for m in raw
    )


def mentions_route(path, query):
    response = timeline_route(path, query)
    if not path.startswith("timelinenew/"):
        return response
    for item in response["response"]["posts"]:
        if int(item["id"]) == MENTIONED_POST:
            item["accountMentions"] = copy.deepcopy(MENTIONS)
    return response


def test_fansly_post_records_its_mentions(fansly, model_db):
    c = FakeSession(mentions_route)

    asyncio.run(scrape_timeline(CREATOR_ID, "samplecreator1", c))

    saved = dict(rows(model_db, "SELECT post_id, mentions FROM posts"))
    assert json.loads(saved.pop(MENTIONED_POST)) == MENTIONS
    # the other two posts tag nobody
    assert sorted(saved.values()) == ["[]", "[]"]


def test_metadata_scan_updates_changed_mentions(monkeypatch, model_db):
    use_site(monkeypatch, "fansly", metadata="check")
    asyncio.run(scrape_timeline(CREATOR_ID, "samplecreator1", FakeSession(timeline_route)))
    asyncio.run(scrape_timeline(CREATOR_ID, "samplecreator1", FakeSession(mentions_route)))

    saved = dict(rows(model_db, "SELECT post_id, mentions FROM posts"))
    assert json.loads(saved[MENTIONED_POST]) == MENTIONS


def test_metadata_update_without_a_mention_list_keeps_the_stored_one(monkeypatch, model_db):
    use_site(monkeypatch, "fansly", metadata="check")
    item = {"id": 7001, "text": "t", "postedAt": "2024-07-03T10:00:00+00:00", "media": []}

    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        tagged = posts_.Post(dict(item, accountMentions=MENTIONS), MODEL_ID, USERNAME, "Timeline")
        await operations.make_post_table_changes([tagged], model_id=MODEL_ID, username=USERNAME)
        untagged = posts_.Post(dict(item, text="edited"), MODEL_ID, USERNAME, "Timeline")
        await operations.make_post_table_changes([untagged], model_id=MODEL_ID, username=USERNAME)

    asyncio.run(run())

    (text, mentions), = rows(model_db, "SELECT text, mentions FROM posts")
    assert text == "edited"
    assert json.loads(mentions) == MENTIONS


def test_onlyfans_message_has_no_conversation_id(onlyfans, model_db, monkeypatch):
    monkeypatch.setattr(post.messages, "get_messages", fetcher([BOUGHT_MESSAGE]))

    asyncio.run(scrape_messages())

    assert rows(model_db, "SELECT post_id, group_id FROM messages") == [(5002, None)]


# ------------------------------------------------------------------ upgrade


def current_layout_before_315(db):
    """A database as the previous version left it: every earlier flag, none of these columns."""
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute("ALTER TABLE posts DROP COLUMN purchase_type")
        conn.execute("ALTER TABLE posts DROP COLUMN mentions")
        conn.execute("ALTER TABLE messages DROP COLUMN group_id")
        conn.executemany(
            "DELETE FROM schema_flags WHERE flag_name = ?", [(f,) for f in NEW_FLAGS]
        )
        conn.execute(
            "INSERT INTO posts (post_id, text, price, paid, archived, pinned, stream, opened,"
            " created_at, model_id) VALUES (5001, 'old post', 3, 1, 0, 0, 0, 1,"
            " '2024-07-01T10:00:00+00:00', ?)",
            (MODEL_ID,),
        )
        conn.execute(
            "INSERT INTO messages (post_id, text, price, paid, archived, created_at, user_id,"
            " model_id) VALUES (100000000000000144, 'old message', 0, 1, 0,"
            " '2024-07-02T10:00:00+00:00', ?, ?)",
            (MODEL_ID, MODEL_ID),
        )
        conn.commit()
    assert get_group_difference(db_path=db) == set(NEW_FLAGS)


def old_schema_backups(db):
    folder = db.parent / "backup"
    return sorted(folder.glob("old_schema_*")) if folder.exists() else []


def test_old_database_is_backed_up_and_upgraded_with_empty_fields(onlyfans, model_db):
    current_layout_before_315(model_db)

    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    # backed up first, in the old layout
    (backup,) = old_schema_backups(model_db)
    assert "purchase_type" not in columns(backup, "posts")
    assert "group_id" not in columns(backup, "messages")
    # upgraded: the new columns are there and the old rows keep their values
    assert not get_group_difference(db_path=model_db)
    assert rows(model_db, "SELECT post_id, text, price, purchase_type, mentions FROM posts") == [
        (5001, "old post", 3, None, None)
    ]
    assert rows(model_db, "SELECT post_id, text, user_id, group_id FROM messages") == [
        (100000000000000144, "old message", MODEL_ID, None)
    ]


def test_upgraded_database_fills_in_the_purchase_type_on_the_next_scan(
    onlyfans, model_db, monkeypatch
):
    current_layout_before_315(model_db)
    monkeypatch.setattr(post.paid, "get_paid_posts", fetcher([BOUGHT_POST]))

    asyncio.run(scrape_paid())

    assert purchase_types(model_db) == [(5001, "post")]
    # the text isn't rewritten outside the metadata command
    assert rows(model_db, "SELECT text FROM posts") == [("old post",)]


def test_upgraded_database_fills_in_the_conversation_on_the_next_scan(fansly, model_db):
    current_layout_before_315(model_db)
    raw = load("messages.json")["response"]
    message = copy.deepcopy(raw["messages"][0])
    message["id"] = "100000000000000144"

    def route(path, query):
        response = messages_route(path, query)
        if path == "message" and "before" not in query:
            response["response"]["messages"] = [message]
        return response

    asyncio.run(scrape_messages(MODEL_ID, USERNAME, FakeSession(route_for(route))))
    assert rows(model_db, "SELECT post_id, group_id FROM messages") == [
        (100000000000000144, GROUP_ID)
    ]


def route_for(route):
    """The messages fixture's conversation is with DM_CREATOR_ID; point it at MODEL_ID."""

    def answer(path, query):
        response = route(path, query)
        if path == "messaging/groups":
            response = copy.deepcopy(response)
            text = json.dumps(response).replace(str(DM_CREATOR_ID), str(MODEL_ID))
            response = json.loads(text)
        return response

    return answer


# ------------------------------------------------------------------ rebuilds and merge


def write_filled_rows(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "INSERT INTO posts (post_id, text, price, paid, archived, pinned, stream, opened,"
            " created_at, model_id, purchase_type, mentions) VALUES (5001, 'p', 3, 1, 0, 0, 0,"
            " 1, '2024-07-01T10:00:00+00:00', ?, 'message', ?)",
            (MODEL_ID, json.dumps(MENTIONS)),
        )
        conn.execute(
            "INSERT INTO messages (post_id, text, price, paid, archived, created_at, user_id,"
            " model_id, group_id) VALUES (5002, 'm', 0, 1, 0, '2024-07-02T10:00:00+00:00',"
            " ?, ?, ?)",
            (MODEL_ID, MODEL_ID, GROUP_ID),
        )
        conn.commit()


FILLED = {
    "posts": [(5001, "message", json.dumps(MENTIONS))],
    "messages": [(5002, GROUP_ID)],
}


def filled(db):
    return {
        "posts": rows(db, "SELECT post_id, purchase_type, mentions FROM posts"),
        "messages": rows(db, "SELECT post_id, group_id FROM messages"),
    }


def test_table_rebuilds_keep_the_new_fields(tmp_path):
    db = tmp_path / "user_data.db"
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)
    write_filled_rows(db)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "DELETE FROM schema_flags WHERE flag_name = ?",
            [("posts_model_id_constraint_added",), ("messages_model_id_constraint_added",)],
        )
        conn.commit()

    call(transition.modify_tables, db_path=db)

    assert not get_group_difference(db_path=db)
    assert filled(db) == FILLED


def test_merge_keeps_the_new_fields(tmp_path):
    source = tmp_path / "old" / "a" / "user_data.db"
    source.parent.mkdir(parents=True)
    call(operations.create_tables, db_path=source)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=source)
    call(write_models_table, model_id=MODEL_ID, db_path=source)
    call(transition.modify_tables, db_path=source, new_db=True)
    write_filled_rows(source)
    target = tmp_path / "new"
    target.mkdir()

    failures, _, _ = asyncio.run(merge.MergeDatabase()(tmp_path / "old", target))

    assert failures == []
    assert filled(target / "user_data.db") == FILLED
