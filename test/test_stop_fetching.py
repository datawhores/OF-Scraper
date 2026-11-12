"""A Stop during a fetch must unwind without publishing a partial scan (#445)."""

import asyncio
import queue
import signal
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ofscraper.commands.check as check
import ofscraper.commands.scraper.scraper as scraper
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.data.api import archive, highlights, labels, messages, paid, pinned, streams, timeline
from ofscraper.data.api.common.cache import write
from ofscraper.data.posts import post


@pytest.fixture(autouse=True)
def stop_signal():
    stop.clear()
    yield
    stop.clear()


@pytest.fixture
def pages(monkeypatch):
    from ofscraper.utils.logs.utils import trace
    monkeypatch.setattr(trace, "settings", SimpleNamespace(get_settings=lambda: SimpleNamespace(
        discord_level="OFF", log_level="OFF", output_level="OFF")))
    monkeypatch.setattr(write.cache, "get", lambda key, default=None: default)
    monkeypatch.setattr(labels, "get_known_label_posts", AsyncMock(return_value={}))
    closed = []
    progress = SimpleNamespace(add_overall_task=Mock(return_value=1),
                               update_overall_task=Mock(), remove_overall_task=Mock())
    monkeypatch.setattr(timeline.progress_utils, "api", progress)

    async def generator(*args, **kwargs):
        try:
            yield [{"id": 1}]
            # A page has arrived, but the next request is still in flight.
            interrupted = asyncio.Event()

            def interrupt():
                try:
                    stop.handle_interrupt(signal.SIGINT, None)
                except KeyboardInterrupt:
                    # Let the baseline fetch finish so pytest reports a failure.
                    pass
                finally:
                    interrupted.set()

            asyncio.get_running_loop().call_soon(interrupt)
            await interrupted.wait()
        finally:
            closed.append(True)

    return generator, closed


def fetch(monkeypatch, area, generator):
    module, entry = {
        "timeline": (timeline, "get_timeline_posts"),
        "archive": (archive, "get_archived_posts"),
        "streams": (streams, "get_streams_posts"),
        "messages": (messages, "get_messages"),
        "paid": (paid, "get_paid_posts"),
        "pinned": (pinned, "get_pinned_posts"),
        "stories": (highlights, "get_stories_post"),
        "highlights": (highlights, "get_highlight_post"),
        "labels": (labels, "get_labels"),
        "label-posts": (labels, "get_labels"),
        "highlight-posts": (highlights, "get_highlight_post"),
        "all-paid": (paid, "get_all_paid_posts"),
    }[area]
    if area in {"timeline", "archive", "streams", "messages"}:
        monkeypatch.setattr(module, "get_after", AsyncMock(return_value=0))
        monkeypatch.setattr(module, "time_log", Mock())
        split = ([], None) if area == "messages" else []
        monkeypatch.setattr(module, "get_split_array", AsyncMock(return_value=split))
        monkeypatch.setattr(module, "get_tasks", lambda *args: [generator()])
    elif area == "paid":
        monkeypatch.setattr(paid, "scrape_paid", generator)
    elif area == "pinned":
        monkeypatch.setattr(pinned, "scrape_pinned_posts", generator)
    elif area == "stories":
        monkeypatch.setattr(highlights, "scrape_stories", generator)
    elif area == "highlights":
        async def highlight_ids(*args):
            async for batch in generator():
                yield [item["id"] for item in batch]
        monkeypatch.setattr(highlights, "scrape_highlight_list", highlight_ids)
        monkeypatch.setattr(highlights, "scrape_highlights_from_list", generator)
    elif area == "highlight-posts":
        monkeypatch.setattr(highlights, "get_highlight_list", AsyncMock(return_value=[1]))
        monkeypatch.setattr(highlights, "scrape_highlights_from_list", generator)
    elif area in {"labels", "label-posts"}:
        if area == "labels":
            monkeypatch.setattr(labels, "scrape_labels", generator)
        else:
            monkeypatch.setattr(labels, "get_labels_data", AsyncMock(return_value=[{"id": 1}]))

        async def label_posts(c, label, *args, **kwargs):
            async for batch in generator():
                yield label, batch
        monkeypatch.setattr(labels, "scrape_posts_labels", label_posts)
    else:
        @asynccontextmanager
        async def session(**kwargs):
            yield object()
        monkeypatch.setattr(paid.manager, "Manager", SimpleNamespace(
            session=SimpleNamespace(aget_ofsession=session)))
        monkeypatch.setattr(paid, "create_tasks_scrape_paid", AsyncMock(side_effect=lambda c: [generator()]))
    args = () if area == "all-paid" else (
        ("a creator", 1) if area == "paid" else
        (1, "a creator") if area in {"timeline", "archive", "streams", "messages"} else (1,)
    )
    return lambda: getattr(module, entry)(*args)


def run_fetch(call):
    async def go():
        return await call()
    return asyncio.run(go())


@pytest.mark.parametrize("area", ["timeline", "archive", "streams", "messages", "paid",
                                  "pinned", "stories", "highlights", "labels", "all-paid",
                                  "highlight-posts", "label-posts"])
def test_stop_cancels_pages_without_saving_cache(monkeypatch, pages, area):
    generator, closed = pages
    saved = Mock()
    monkeypatch.setattr(write.cache, "set", saved)
    call = fetch(monkeypatch, area, generator)

    async def go():
        with stop.interrupt_handler():
            with pytest.raises(stop.DownloadsStopped):
                await asyncio.wait_for(call(), 2)
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    asyncio.run(go())
    assert closed == [True]
    saved.assert_not_called()


@pytest.mark.parametrize("menu", [True, False], ids=["menu", "cli"])
def test_first_interrupt_returns_or_exits_without_downloading(monkeypatch, pages, menu, caplog):
    generator, closed = pages
    fetch(monkeypatch, "messages", generator)
    download = Mock()
    final = Mock()
    markers = Mock()
    monkeypatch.setattr(post, "set_after_checks", markers)
    monkeypatch.setattr(post.settings, "get_settings", lambda: SimpleNamespace(post_id=[], system_free_min=0))
    monkeypatch.setattr(scraper, "final_action", final)

    def runner(self, menu=False):
        async def go():
            # Exercise the real area wrapper: it must never reach set_after_checks.
            await post.process_messages(1, "a creator", None)
            download()
        asyncio.run(go())

    monkeypatch.setattr(scraper.scraperManager, "_runner", runner)
    previous = signal.getsignal(signal.SIGINT)
    if menu:
        scraper.scraperManager().runner(menu=True)
    else:
        with pytest.raises(SystemExit) as exc:
            scraper.scraperManager().runner()
        assert exc.value.code == 130
    assert signal.getsignal(signal.SIGINT) == previous
    assert closed == [True]
    download.assert_not_called()
    markers.assert_not_called()
    final.assert_called_once()
    assert "Stopping the fetch. A second Ctrl+C quits." in caplog.text
    assert "second Ctrl+C quits" in caplog.text


def test_second_interrupt_quits_during_fetch():
    async def go():
        @stop.fetching
        async def fetching():
            stop.handle_interrupt(signal.SIGINT, None)
            with pytest.raises(KeyboardInterrupt):
                stop.handle_interrupt(signal.SIGINT, None)
            await asyncio.sleep(0)
        with pytest.raises(stop.DownloadsStopped):
            await fetching()
    asyncio.run(go())


@pytest.mark.parametrize("writer", [lambda: write.set_after_checks(1, "Messages"),
                                    lambda: write.set_check_mode_posts(1, "Messages", []),
                                    lambda: labels.commit_finished_labels(1)])
def test_pending_stop_cannot_advance_completion_state(monkeypatch, writer):
    saved = Mock()
    monkeypatch.setattr(write.cache, "set", saved)
    labels.mark_label_finished(1, 2)
    try:
        stop.request()
        with pytest.raises(asyncio.CancelledError):
            writer()
        saved.assert_not_called()
    finally:
        labels.discard_finished_labels(1)


@pytest.mark.parametrize("menu", [True, False], ids=["menu", "cli"])
def test_check_fetch_stops_before_table_opens(monkeypatch, pages, menu):
    generator, closed = pages
    call = fetch(monkeypatch, "paid", generator)
    monkeypatch.setattr(check, "check_auth", Mock())
    monkeypatch.setattr(check, "allow_check_dupes", Mock())
    monkeypatch.setattr(check, "set_after_check_mode", Mock())
    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(command="paid_check"))
    table = Mock()
    monkeypatch.setattr(check, "start_helper", table)
    monkeypatch.setattr(check, "purchase_checker_runner", lambda: run_fetch(call))
    if menu:
        check.checker(menu=True)
    else:
        with pytest.raises(SystemExit) as exc:
            check.checker()
        assert exc.value.code == 130
    assert closed == [True]
    table.assert_not_called()


def test_daemon_fetch_stop_shuts_down_scheduler(monkeypatch, pages):
    from test.test_daemon_shutdown import _stub_daemon
    generator, closed = pages
    call = fetch(monkeypatch, "paid", generator)
    manager = scraper.scraperManager()
    monkeypatch.setattr(manager, "_runner", lambda menu=False: run_fetch(call))
    monkeypatch.setattr(scraper, "final_action", Mock())
    jobs = queue.Queue()
    _stub_daemon(monkeypatch, jobs, manager.runner)
    clear = Mock()
    monkeypatch.setattr(scraper.schedule, "clear", clear)
    with pytest.raises(SystemExit) as exc:
        scraper.daemon_process()
    assert exc.value.code == 130
    assert closed == [True]
    assert jobs.unfinished_tasks == 0
    clear.assert_called_once()


def test_stopped_area_cancels_siblings_and_discards_label_completion(monkeypatch, pages):
    generator, closed = pages
    call = fetch(monkeypatch, "messages", generator)
    sibling_closed = []
    saved = Mock()
    monkeypatch.setattr(write.cache, "set", saved)
    monkeypatch.setattr(post, "batch_mediainsert", AsyncMock())

    async def sibling():
        try:
            labels.mark_label_finished(1, 2)
            await asyncio.Event().wait()
        finally:
            sibling_closed.append(True)

    async def tasks(*args, **kwargs):
        stop.create_fetch_task(sibling())
        return await call()

    monkeypatch.setattr(post, "process_tasks", tasks)

    async def go():
        with stop.interrupt_handler():
            with pytest.raises(stop.DownloadsStopped):
                await post.process_areas(SimpleNamespace(name="a creator"), 1, "a creator")
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    asyncio.run(go())
    assert closed == sibling_closed == [True]
    assert 1 not in labels._finished_labels
    saved.assert_not_called()
    post.batch_mediainsert.assert_not_called()


@pytest.mark.parametrize("command,runner,retriever", [
    ("post_check", "post_check_runner", "post_check_retriver"),
    ("msg_check", "message_checker_runner", "message_check_retriver"),
    ("paid_check", "purchase_checker_runner", "purchase_check_retriver"),
    ("story_check", "stories_checker_runner", "stories_check_retriver"),
])
def test_check_fetch_remains_stoppable_until_rows_are_ready(monkeypatch, command, runner, retriever):
    async def rows():
        row = ("a creator", 1, [])
        yield row if command == "story_check" else (*row, False)

    async def gather(*args):
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
        await asyncio.sleep(0)

    monkeypatch.setattr(check, retriever, rows)
    monkeypatch.setattr(check, "process_post_media", AsyncMock())
    monkeypatch.setattr(check, "make_changes_to_content_tables", AsyncMock())
    monkeypatch.setattr(check, "row_gather", gather)
    monkeypatch.setattr(check, "check_auth", Mock())
    monkeypatch.setattr(check, "allow_check_dupes", Mock())
    monkeypatch.setattr(check, "set_after_check_mode", Mock())
    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(command=command))
    monkeypatch.setattr(check.progress_utils, "setup_live", lambda *a, **k: nullcontext())
    monkeypatch.setattr(check.progress_updater, "activity", Mock(desc=None))
    table = Mock()
    monkeypatch.setattr(check, "start_helper", table)
    real_runner = getattr(check, runner)
    monkeypatch.setattr(check, runner, lambda: run_fetch(real_runner))
    check.checker(menu=True)
    table.assert_not_called()


def test_stop_checked_before_scheduled_cancel_still_cleans_workers():
    closed = []

    async def worker():
        try:
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    @stop.fetching
    async def fetching():
        stop.create_fetch_task(worker())
        await asyncio.sleep(0)
        stop.handle_interrupt(signal.SIGINT, None)
        stop.check()

    async def go():
        with pytest.raises(stop.DownloadsStopped):
            await fetching()
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]

    asyncio.run(go())
    assert closed == [True]
