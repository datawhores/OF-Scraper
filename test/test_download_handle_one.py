"""The per-file step of the download loop is one function, ``handle_one``,
so a worker that takes items from somewhere other than a list (the Fansly
page-by-page download) runs the same step. The loop over a list,
``consumer``, calls it."""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.download import stop

COUNTERS = (
    "photo_count", "video_count", "audio_count", "skipped", "forced_skipped",
    "stopped", "total_bytes_downloaded", "total_bytes",
)


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


class Item:
    def __init__(self, id):
        self.id = id
        self.marked = None

    def mark_download_succeeded(self):
        self.marked = "succeeded"

    def mark_download_failed(self):
        self.marked = "failed"

    def mark_download_skipped(self):
        self.marked = "skipped"


async def _noop(*a, **k):
    return None


@pytest.fixture
def env(monkeypatch):
    common_globals.set_up_contexvars()
    for name in COUNTERS:
        monkeypatch.setattr(common_globals, name, 0, raising=False)
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)
    shown = []

    def update(task, description=None, **k):
        shown.append(description)

    monkeypatch.setattr(
        run_mod, "progress_updater",
        SimpleNamespace(download=SimpleNamespace(update_overall_task=update)),
    )
    monkeypatch.setattr(run_mod, "desc", "{mediacount}")
    monkeypatch.setattr(run_mod, "log_download_progress", lambda *a: None)
    monkeypatch.setattr(
        run_mod, "asyncio",
        SimpleNamespace(sleep=_noop, CancelledError=asyncio.CancelledError),
    )
    monkeypatch.setattr(run_mod.fansly_video, "uses_stream", lambda ele: False)
    stop.clear()
    yield SimpleNamespace(shown=shown)
    stop.clear()


def test_counts_the_result_and_shows_the_total_at_that_moment(env, monkeypatch):
    async def download(c, ele, model_id, username):
        return ("images" if ele.id == 1 else "skipped"), 10

    monkeypatch.setattr(run_mod, "download", download)
    queued = [Item(1)]
    results = []

    async def go():
        assert await run_mod.handle_one(
            (None, queued[0], 1, "a"), None, lambda: len(queued),
            on_result=lambda ele, r: results.append((ele.id, r)),
        )
        queued.append(Item(2))
        assert await run_mod.handle_one(
            (None, queued[1], 1, "a"), None, lambda: len(queued),
            on_result=lambda ele, r: results.append((ele.id, r)),
        )

    asyncio.run(go())
    assert results == [(1, "downloaded"), (2, "failed")]
    assert [i.marked for i in queued] == ["succeeded", "failed"]
    assert common_globals.photo_count == 1 and common_globals.skipped == 1
    assert common_globals.total_bytes_downloaded == 20
    # the count shown grows as items are added
    assert env.shown == ["1", "2"]


def test_an_item_stopped_before_it_started_ends_the_worker(env, monkeypatch):
    async def download(c, ele, model_id, username):
        stop.request()
        await asyncio.sleep(0)
        raise asyncio.CancelledError

    monkeypatch.setattr(run_mod, "download", download)
    item = Item(1)
    assert asyncio.run(run_mod.handle_one((None, item, 1, "a"), None, lambda: 1)) is False
    assert item.download_unstarted is True
    assert env.shown == []


def test_an_item_with_no_link_fails_with_a_plain_reason(env, monkeypatch):
    # locked media sent from the check table has no url and no mpd; the
    # download returned None and handle_one crashed on len(None)
    calls = []

    class _Recorder:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, a[0] if a else None))

    monkeypatch.setattr(common_globals, "log", _Recorder(), raising=False)
    monkeypatch.setattr(run_mod, "fresh_before_download", _noop)
    monkeypatch.setattr(run_mod, "get_medialog", lambda ele: "media")
    item = Item(1)
    item.url = item.mpd = None
    results = []

    asyncio.run(
        run_mod.handle_one(
            (None, item, 1, "a"), None, lambda: 1,
            on_result=lambda ele, r: results.append(r),
        )
    )
    assert results == ["failed"] and item.marked == "failed"
    assert ("info", "media Not downloaded: it has no link (locked or removed)") in calls
    assert not [name for name, _ in calls if name == "traceback_"]


def test_consumer_runs_each_item_through_handle_one(env, monkeypatch):
    seen = []

    async def handle_one(data, task1, total, on_result=None):
        seen.append((data[1], total(), on_result))
        return data[1] != "stop here"

    monkeypatch.setattr(run_mod, "handle_one", handle_one)
    marker = object()
    medialist = ["a", "stop here", "b"]
    aws = [(None, ele, 1, "u") for ele in medialist]

    async def go():
        await run_mod.consumer(aws, None, medialist, asyncio.Lock(), on_result=marker)

    asyncio.run(go())
    # items are taken from the end of the list; False ends the worker
    assert seen == [("b", 3, marker), ("stop here", 3, marker)]
    assert aws == [(None, "a", 1, "u")]
