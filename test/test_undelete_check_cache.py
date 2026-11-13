"""The check commands clear the deleted flag only for what they fetched (#323).

A check without --force reads each area from the check cache, which can be
days old and can hold posts and messages the creator deleted since. Those must
stay deleted. The check tests run the command's real runner and retriever into
a real SQLite database in a temporary folder. Only the network, the progress
display and the UI table are replaced, and any API call the test doesn't expect
fails. Two more tests check which save calls say their items came from the API.
"""

import ast
import asyncio
import contextlib
import pathlib
from types import SimpleNamespace

import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.data.posts.post as scan_post
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.check as check
import ofscraper.db.operations as operations
import ofscraper.db.operations_.messages as messages
import ofscraper.db.operations_.posts as posts
import ofscraper.utils.settings as settings

MODEL_ID = 32301
USERNAME = "checkmodel"
CACHED = 2001
FRESH = 2002
DATE = "2024-03-01T10:00:00+00:00"


def post_item(post_id, **fields):
    return {"id": post_id, "text": "a post", "price": 0, "postedAt": DATE, "media": [],
            **fields}


def message_item(post_id):
    return {"id": post_id, "text": "a message", "price": 0, "createdAt": DATE,
            "fromUser": {"id": MODEL_ID}, "media": []}


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
        site="onlyfans", force=False, metadata=None, check_usernames=[USERNAME],
        file_usernames=None, file=None, url=[USERNAME],
        check_area=["Timeline", "Archived", "Pinned", "Labels", "Streams"],
        timeline_strict=False,
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
    return monkeypatch


def use_cache(env, cache):
    # areas missing from the cache are fetched fresh
    env.setattr(check, "read_check", lambda model_id, api: cache.get(api))


def deleted_posts():
    return posts.get_deleted_post_ids(model_id=MODEL_ID, username=USERNAME)


def deleted_messages():
    return messages.get_deleted_messages_ids(model_id=MODEL_ID, username=USERNAME)


async def flagged_posts(*items):
    # an earlier scan saved the posts, then a later one flagged them deleted
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await posts.make_post_table_changes(
        [posts_.Post(item, MODEL_ID, USERNAME, "Timeline") for item in items],
        model_id=MODEL_ID, username=USERNAME, from_api=True,
    )
    ids = [item["id"] for item in items]
    await posts.mark_post_as_deleted(ids, model_id=MODEL_ID, username=USERNAME)
    assert await deleted_posts() == set(ids)


async def flagged_messages(*items):
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await messages.make_messages_table_changes(
        [posts_.Post(item, MODEL_ID, USERNAME, "Messages") for item in items],
        model_id=MODEL_ID, username=USERNAME, from_api=True,
    )
    ids = [item["id"] for item in items]
    await messages.mark_message_as_deleted(ids, model_id=MODEL_ID, username=USERNAME)
    assert await deleted_messages() == set(ids)


AREA_FIELDS = {
    "Timeline": {},
    "Archived": {"isArchived": True},
    "Pinned": {"isPinned": True},
    "Streams": {"streamId": 77},
}


@pytest.mark.parametrize("area", [*AREA_FIELDS, "Labels"])
def test_post_check_from_the_cache_keeps_a_deleted_post_deleted(check_env, area):
    if area == "Labels":
        cached = [post_item(CACHED)]
    else:
        cached = [post_item(CACHED, **AREA_FIELDS[area])]
    cache = {name: [] for name in ["Timeline", "Archived", "Pinned", "Labels", "Streams"]}
    cache[area] = cached
    use_cache(check_env, cache)

    async def run():
        await flagged_posts(post_item(CACHED))
        await check.post_check_runner()
        return await deleted_posts()

    assert asyncio.run(run()) == {CACHED}


def test_post_check_clears_only_the_posts_it_fetched(check_env):
    # the timeline is fetched fresh and returns FRESH again; the archived list
    # comes from the cache and still holds CACHED, which the creator deleted
    async def timeline_api(*args, **kwargs):
        return [post_item(FRESH)]

    check_env.setattr(check.timeline, "get_timeline_posts", timeline_api)
    use_cache(
        check_env,
        {"Archived": [post_item(CACHED, isArchived=True)], "Pinned": [], "Labels": [],
         "Streams": []},
    )

    async def run():
        await flagged_posts(post_item(CACHED), post_item(FRESH))
        await check.post_check_runner()
        return await deleted_posts()

    assert asyncio.run(run()) == {CACHED}


def test_message_check_from_the_cache_keeps_a_deleted_message_deleted(check_env):
    use_cache(check_env, {"Messages": [message_item(CACHED)], "Purchased": []})

    async def run():
        await flagged_messages(message_item(CACHED))
        await check.message_checker_runner()
        return await deleted_messages()

    assert asyncio.run(run()) == {CACHED}


def test_message_check_clears_a_message_it_fetched(check_env):
    async def messages_api(*args, **kwargs):
        return [message_item(FRESH)]

    check_env.setattr(check.messages_, "get_messages", messages_api)
    use_cache(check_env, {"Purchased": []})

    async def run():
        await flagged_messages(message_item(FRESH))
        await check.message_checker_runner()
        return await deleted_messages()

    assert asyncio.run(run()) == set()


SAVES = {"make_post_table_changes", "make_messages_table_changes", "make_label_table_changes"}


def save_calls(module):
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", getattr(node.func, "id", None)) in SAVES
    ]


def from_api(call):
    return next((kw.value for kw in call.keywords if kw.arg == "from_api"), None)


def test_every_scan_area_saves_its_items_as_from_the_api():
    # timeline, archived, streams, pinned, labels, messages, paid and scrape paid
    calls = save_calls(scan_post)
    assert len(calls) == 8
    for call in calls:
        value = from_api(call)
        assert isinstance(value, ast.Constant) and value.value is True, ast.unparse(call)


def test_saving_already_collected_posts_never_clears_the_flag():
    # check runners and manual downloads save posts they already have
    calls = save_calls(operations)
    assert len(calls) == 3
    for call in calls:
        assert from_api(call) is None, ast.unparse(call)


def test_purchase_check_from_the_cache_keeps_a_deleted_post_deleted(check_env):
    use_cache(check_env, {"Purchased": [post_item(CACHED, responseType="post")]})

    async def run():
        await flagged_posts(post_item(CACHED))
        await check.purchase_checker_runner()
        return await deleted_posts()

    assert asyncio.run(run()) == {CACHED}
