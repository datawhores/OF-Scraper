"""Check-table activity and API progress display."""

# ----------------------------------------------------------------------
# From test_check_activity.py
# Check fetches restore the activity shown before opening the table.
# ----------------------------------------------------------------------

import asyncio
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from rich.progress import Progress

import ofscraper.commands.check as check
from ofscraper.utils.live.updater import ActivityManager


@pytest.mark.parametrize(
    "runner_name,retriever_name,command,activity_label",
    [
        ("post_check_runner", "post_check_retriver", "post_check", "Timeline posts"),
        ("message_checker_runner", "message_check_retriver", "msg_check", "Messages"),
        ("purchase_checker_runner", "purchase_check_retriver", "paid_check", "Purchased posts"),
        ("stories_checker_runner", "stories_check_retriver", "story_check", "Stories posts"),
    ],
)
@pytest.mark.parametrize("fetch_error", [False, True])
@pytest.mark.parametrize("previous_visible", [False, True])
@pytest.mark.parametrize("refill", [False, True], ids=["runner", "cart-refresh"])
def test_check_fetch_restores_activity(
    monkeypatch, runner_name, retriever_name, command, activity_label,
    fetch_error, previous_visible, refill,
):
    progress = Progress()
    task_id = progress.add_task(
        "Previous activity", total=10, completed=3, visible=previous_visible
    )
    activity = ActivityManager(progress, None, lambda: task_id, None, None)
    checking = check.check_str.format(username="<creator>", activity=activity_label)
    calls = []

    async def retriever(*args, **kwargs):
        calls.append(kwargs)
        activity.update_task(description=checking, visible=True)
        await asyncio.sleep(0)
        if fetch_error:
            raise RuntimeError("fetch failed")
        result = ("<creator>", 1, [])
        yield result if command == "story_check" else (*result, None)

    async def no_op(*args, **kwargs):
        pass

    monkeypatch.setattr(check.progress_updater, "activity", activity)
    monkeypatch.setattr(check.progress_utils, "setup_live", lambda *a, **kw: nullcontext())
    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(command=command))
    monkeypatch.setattr(check, retriever_name, retriever)
    for name in ["process_post_media", "make_changes_to_content_tables", "row_gather"]:
        monkeypatch.setattr(check, name, no_op)

    async def run():
        if refill:
            await check.data_refill(1)
        else:
            await getattr(check, runner_name)()

    if fetch_error:
        with pytest.raises(RuntimeError, match="fetch failed"):
            asyncio.run(run())
    else:
        asyncio.run(run())

    assert len(calls) == 1
    task = progress.tasks[0]
    assert task.description == "Previous activity"
    assert task.visible == previous_visible
    assert (task.completed, task.total) == (3, 10)

# ----------------------------------------------------------------------
# From test_check_api_progress.py
# Check-table API progress is visible before retrievers yield (#438).
# ----------------------------------------------------------------------

import asyncio
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check


@pytest.mark.parametrize(
    "runner,activity,areas_per_creator",
    [
        (check.post_check_runner, "Timeline posts", 5),
        (check.message_checker_runner, "Messages", 2),
        (check.purchase_checker_runner, "Purchased posts", 1),
        (check.stories_checker_runner, "Stories posts", 2),
    ],
)
@pytest.mark.parametrize("fetch_error", [False, True])
def test_api_progress_during_check_fetch(
    monkeypatch, runner, activity, areas_per_creator, fetch_error
):
    creators = ["creator_one", "creator_two"]
    state = SimpleNamespace(
        live=False, description="", creator=None, calls=0,
        id=0, completed=0, total=None, visible=False,
    )

    @contextmanager
    def screen(name):
        assert name == "api"
        assert not state.live
        state.live = True
        try:
            yield
        finally:
            state.live = False

    def update_task(visible=True, **kwargs):
        state.visible = visible
        for key, value in kwargs.items():
            setattr(state, key, value)

    def get_id(name, asked_for=None):
        state.creator = name
        return creators.index(name) + 1

    @asynccontextmanager
    async def session(**kwargs):
        yield None

    async def fetch(*args, **kwargs):
        # Real retrievers reach these API boundaries before yielding to runners.
        assert state.live, "API screen must be open while fetching"
        assert state.visible
        assert state.description == check.check_str.format(
            username=state.creator, activity=activity
        )
        state.calls += 1
        await asyncio.sleep(0)
        if fetch_error:
            raise RuntimeError("fetch failed")
        return []

    async def no_op(*args, **kwargs):
        pass

    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(
        force=True, check_area=["Timeline", "Archived", "Pinned", "Labels", "Streams"]
    ))
    monkeypatch.setattr(check, "url_helper", lambda: iter(creators))
    monkeypatch.setattr(check, "check_usernames", lambda: creators)
    monkeypatch.setattr(check.profile, "get_id", get_id)
    monkeypatch.setattr(check.profile, "scrape_profile", lambda name: {"username": name})
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(
        session=SimpleNamespace(aget_ofsession=session)
    ))
    monkeypatch.setattr(check.progress_utils, "setup_live", screen)
    monkeypatch.setattr(check.progress_updater, "activity", SimpleNamespace(
        update_task=update_task, desc=SimpleNamespace(tasks=[state]),
        get_desc_id=lambda: 0,
    ))
    monkeypatch.setattr(check.auth_requests, "make_headers", lambda: None)
    monkeypatch.setattr(check, "read_check", lambda *args: None)
    monkeypatch.setattr(check, "set_check", lambda *args: None)
    monkeypatch.setattr(check.timeline, "filter_timeline_post", lambda posts: posts)
    for module, name in [
        (check.timeline, "get_timeline_posts"),
        (check.archived, "get_archived_posts"),
        (check.pinned, "get_pinned_posts"),
        (check.labels, "get_labels"),
        (check.streams, "get_streams_posts"),
        (check.messages_, "get_messages"),
        (check.paid_, "get_paid_posts"),
        (check.highlights, "get_stories_post"),
        (check.highlights, "get_highlight_post"),
    ]:
        monkeypatch.setattr(module, name, fetch)
    for name in ["table_init_create", "make_post_table_changes",
                 "make_messages_table_changes", "make_label_table_changes"]:
        monkeypatch.setattr(check.operations, name, no_op)
    for name in ["process_post_media", "make_changes_to_content_tables", "row_gather"]:
        monkeypatch.setattr(check, name, no_op)

    async def run():
        if fetch_error:
            with pytest.raises(RuntimeError, match="fetch failed"):
                await runner()
        else:
            await runner()

    asyncio.run(run())
    assert not state.live
    assert state.calls == (1 if fetch_error else 2 * areas_per_creator)
