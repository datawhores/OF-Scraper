"""A check run from the check cache with --metadata doesn't write the cached
copy over newer rows (#340).

A check without --force reads each area from the check cache, which can be
days old. With --metadata, the existing rows of items fetched from the API in
this run are updated as before; rows of items that came only from the cache
are left alone, and items the database doesn't have yet are still saved. The
tests run the command's real runner and retriever into a real SQLite database
in a temporary folder. Only the network, the progress display and the UI table
are replaced, and any API call the test doesn't serve fails.
"""

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.check as check
import ofscraper.db.operations as operations
import ofscraper.db.operations_.messages as messages
import ofscraper.db.operations_.posts as posts
import ofscraper.utils.settings as settings

MODEL_ID = 34001
USERNAME = "checkmodel"
CACHED = 4001
FRESH = 4002
NEW = 4003
OLD_DATE = "2024-03-01T10:00:00+00:00"
NEW_DATE = "2024-09-01T10:00:00+00:00"

AREAS = ["Timeline", "Archived", "Pinned", "Labels", "Streams"]
AREA_FIELDS = {
    "Timeline": {},
    "Archived": {"isArchived": True},
    "Pinned": {"isPinned": True},
    "Labels": {},
    "Streams": {"streamId": 77},
}


def post_item(post_id, text, date, price=0, area="Timeline", **fields):
    return {"id": post_id, "text": text, "price": price, "postedAt": date,
            "media": [], **AREA_FIELDS[area], **fields}


def message_item(post_id, text, date, price=0):
    return {"id": post_id, "text": text, "price": price, "createdAt": date,
            "fromUser": {"id": MODEL_ID}, "media": []}


# what the cache still holds, and what a later scan saved
def old_post(post_id, area="Timeline", **fields):
    return post_item(post_id, "old text", OLD_DATE, area=area, **fields)


def new_post(post_id, area="Timeline", **fields):
    return post_item(post_id, "new text", NEW_DATE, price=5, area=area, **fields)


@pytest.fixture
def check_env(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(
        site="onlyfans", force=False, metadata="check", check_usernames=[USERNAME],
        file_usernames=None, file=None, url=[USERNAME], check_area=AREAS,
        timeline_strict=False, mediatypes=["Images"],
    )
    monkeypatch.setattr(settings, "get_settings", lambda: stub)

    @contextlib.asynccontextmanager
    async def session(*args, **kwargs):
        yield None

    async def no_rows(*args, **kwargs):
        return None

    async def api_call(*args, **kwargs):
        raise AssertionError("the check called the API for a cached area")

    for module, name in [
        (check.timeline, "get_timeline_posts"),
        (check.archived, "get_archived_posts"),
        (check.pinned, "get_pinned_posts"),
        (check.labels, "get_labels"),
        (check.streams, "get_streams_posts"),
        (check.messages_, "get_messages"),
        (check.paid_, "get_paid_posts"),
    ]:
        monkeypatch.setattr(module, name, api_call)
    monkeypatch.setattr(
        check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=session))
    )
    monkeypatch.setattr(check.auth_requests, "make_headers", lambda *a, **k: None)
    monkeypatch.setattr(check.profile, "scrape_profile", lambda *a, **k: {"username": USERNAME})
    monkeypatch.setattr(check.profile, "get_id", lambda *a, **k: MODEL_ID)
    monkeypatch.setattr(check, "set_check", lambda *a, **k: None)
    monkeypatch.setattr(check, "row_gather", no_rows)
    monkeypatch.setattr(check.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    monkeypatch.setattr(
        check.progress_updater, "activity", SimpleNamespace(update_task=lambda *a, **k: None, desc=None, get_desc_id=lambda: None)
    )
    monkeypatch.setattr(check, "check_user_dict", check.defaultdict(dict))
    return SimpleNamespace(monkeypatch=monkeypatch, db=db)


def use_cache(env, cache):
    # areas missing from the cache are fetched fresh
    env.monkeypatch.setattr(check, "read_check", lambda model_id, api: cache.get(api))


def serve(env, module, name, items):
    async def api(*args, **kwargs):
        return items

    env.monkeypatch.setattr(module, name, api)


def dump(db, table="posts"):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.row_factory = sqlite3.Row
        return {
            row["post_id"]: dict(row)
            for row in conn.execute(f"SELECT * FROM {table} ORDER BY post_id")
        }


async def saved_posts(*items, deleted=(), purchased=False):
    # a later scan saved the newer copies, and flagged some deleted
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await posts.make_post_table_changes(
        [posts_.Post(item, MODEL_ID, USERNAME, purchased=purchased) for item in items],
        model_id=MODEL_ID, username=USERNAME, from_api=True,
    )
    if deleted:
        await posts.mark_post_as_deleted(list(deleted), model_id=MODEL_ID, username=USERNAME)


async def saved_messages(*items, deleted=()):
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await messages.make_messages_table_changes(
        [posts_.Post(item, MODEL_ID, USERNAME, "Messages") for item in items],
        model_id=MODEL_ID, username=USERNAME, from_api=True,
    )
    if deleted:
        await messages.mark_message_as_deleted(
            list(deleted), model_id=MODEL_ID, username=USERNAME
        )


def run_check(env, setup, runner, table="posts"):
    async def run():
        await setup()
        before = dump(env.db, table)
        await runner()
        return before

    before = asyncio.run(run())
    return before, dump(env.db, table)


def empty_cache():
    return {area: [] for area in AREAS}


@pytest.mark.parametrize("area", AREAS)
def test_post_check_from_the_cache_leaves_the_row_alone(check_env, area):
    cache = empty_cache()
    cache[area] = [old_post(CACHED, area)]
    use_cache(check_env, cache)

    before, after = run_check(
        check_env,
        lambda: saved_posts(new_post(CACHED, area), deleted=[CACHED]),
        check.post_check_runner,
    )
    assert before[CACHED]["is_deleted"] == 1
    assert before[CACHED]["text"] == "new text"
    # text, price, dates and the deleted flag are all as the later scan left them
    assert after == before


@pytest.mark.parametrize("area", AREAS)
def test_post_check_updates_a_fresh_area_as_before(check_env, area):
    cache = empty_cache()
    del cache[area]
    use_cache(check_env, cache)
    if area == "Labels":
        serve(check_env, check.labels, "get_labels",
              [{"id": 9, "name": "a label", "type": "custom", "posts": [new_post(FRESH)]}])
    else:
        module, name = {
            "Timeline": (check.timeline, "get_timeline_posts"),
            "Archived": (check.archived, "get_archived_posts"),
            "Pinned": (check.pinned, "get_pinned_posts"),
            "Streams": (check.streams, "get_streams_posts"),
        }[area]
        serve(check_env, module, name, [new_post(FRESH, area)])

    before, after = run_check(
        check_env, lambda: saved_posts(old_post(FRESH, area)), check.post_check_runner
    )
    assert after[FRESH] == dict(
        before[FRESH], text="new text", price=5, paid=1, created_at=NEW_DATE
    )


def test_post_check_updates_only_the_fresh_posts(check_env):
    # the timeline is fetched fresh; the archived list comes from the cache
    serve(check_env, check.timeline, "get_timeline_posts", [new_post(FRESH)])
    cache = empty_cache()
    del cache["Timeline"]
    cache["Archived"] = [old_post(CACHED, "Archived")]
    use_cache(check_env, cache)

    before, after = run_check(
        check_env,
        lambda: saved_posts(
            old_post(FRESH), new_post(CACHED, "Archived"), deleted=[CACHED]
        ),
        check.post_check_runner,
    )
    assert after[CACHED] == before[CACHED]
    assert after[FRESH]["text"] == "new text"
    assert after[FRESH]["created_at"] == NEW_DATE


@pytest.mark.parametrize(
    "fresh_area, cached_area",
    [("Timeline", "Archived"), ("Pinned", "Timeline"), ("Archived", "Labels")],
)
def test_a_fresh_copy_of_a_post_wins_over_a_cached_one(check_env, fresh_area, cached_area):
    # the same post is in a fresh area and, older, in a cached one
    module, name = {
        "Timeline": (check.timeline, "get_timeline_posts"),
        "Archived": (check.archived, "get_archived_posts"),
        "Pinned": (check.pinned, "get_pinned_posts"),
    }[fresh_area]
    serve(check_env, module, name, [new_post(FRESH, fresh_area)])
    cache = empty_cache()
    del cache[fresh_area]
    cache[cached_area] = [old_post(FRESH, cached_area)]
    use_cache(check_env, cache)

    before, after = run_check(
        check_env, lambda: saved_posts(old_post(FRESH)), check.post_check_runner
    )
    assert before[FRESH]["text"] == "old text"
    assert after[FRESH]["text"] == "new text"
    assert after[FRESH]["price"] == 5
    assert after[FRESH]["created_at"] == NEW_DATE


def test_post_check_still_saves_a_new_post_from_the_cache(check_env):
    cache = empty_cache()
    cache["Timeline"] = [old_post(CACHED), old_post(NEW)]
    use_cache(check_env, cache)

    before, after = run_check(
        check_env, lambda: saved_posts(new_post(CACHED)), check.post_check_runner
    )
    assert NEW not in before
    assert after[NEW]["text"] == "old text"
    assert after[NEW]["created_at"] == OLD_DATE
    assert after[CACHED] == before[CACHED]


def test_message_check_from_the_cache_leaves_the_row_alone(check_env):
    use_cache(
        check_env,
        {"Messages": [message_item(CACHED, "old text", OLD_DATE)], "Purchased": []},
    )

    before, after = run_check(
        check_env,
        lambda: saved_messages(
            message_item(CACHED, "new text", NEW_DATE, price=5), deleted=[CACHED]
        ),
        check.message_checker_runner,
        table="messages",
    )
    assert before[CACHED]["is_deleted"] == 1
    assert after == before


def test_message_check_updates_fresh_messages_as_before(check_env):
    serve(check_env, check.messages_, "get_messages",
          [message_item(FRESH, "new text", NEW_DATE, price=5)])
    use_cache(check_env, {"Purchased": []})

    before, after = run_check(
        check_env,
        lambda: saved_messages(message_item(FRESH, "old text", OLD_DATE)),
        check.message_checker_runner,
        table="messages",
    )
    assert after[FRESH] == dict(
        before[FRESH], text="new text", price=5, paid=1, created_at=NEW_DATE
    )


def test_message_check_still_saves_a_new_message_from_the_cache(check_env):
    use_cache(
        check_env,
        {"Messages": [message_item(CACHED, "old text", OLD_DATE),
                      message_item(NEW, "old text", OLD_DATE)],
         "Purchased": []},
    )

    before, after = run_check(
        check_env,
        lambda: saved_messages(message_item(CACHED, "new text", NEW_DATE, price=5)),
        check.message_checker_runner,
        table="messages",
    )
    assert NEW not in before
    assert after[NEW]["text"] == "old text"
    assert after[CACHED] == before[CACHED]


def test_message_check_leaves_a_cached_purchase_alone(check_env):
    use_cache(
        check_env,
        {"Messages": [], "Purchased": [old_post(CACHED, responseType="post")]},
    )

    before, after = run_check(
        check_env,
        # saved as bought already, so only --metadata could change the row
        lambda: saved_posts(
            new_post(CACHED, responseType="post"), deleted=[CACHED], purchased=True
        ),
        check.message_checker_runner,
    )
    assert after == before


@pytest.mark.parametrize("fresh", [False, True])
def test_purchase_check_updates_only_a_fresh_list(check_env, fresh):
    if fresh:
        serve(check_env, check.paid_, "get_paid_posts",
              [new_post(CACHED, responseType="post")])
        use_cache(check_env, {})
    else:
        use_cache(check_env, {"Purchased": [old_post(CACHED, responseType="post")]})

    before, after = run_check(
        check_env,
        lambda: saved_posts(
            post_item(CACHED, "older text", OLD_DATE) if fresh
            else new_post(CACHED, responseType="post"),
            purchased=True,
        ),
        check.purchase_checker_runner,
    )
    if fresh:
        assert after[CACHED]["text"] == "new text"
        assert after[CACHED]["created_at"] == NEW_DATE
    else:
        assert after == before
