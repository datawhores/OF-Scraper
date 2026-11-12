"""Check fetches restore the activity shown before opening the table."""

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
