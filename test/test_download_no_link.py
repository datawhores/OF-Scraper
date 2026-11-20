"""An item with no link (no url, no mpd) used to make ``download()`` return
None, and the download loop crashed on ``len(None)``: a TypeError traceback
in the log and no reason given. It now fails with a plain reason."""

import asyncio
from types import SimpleNamespace

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.download import stop

COUNTERS = (
    "photo_count", "video_count", "audio_count", "skipped", "forced_skipped",
    "stopped", "total_bytes_downloaded", "total_bytes",
)


class Item:
    def __init__(self, id):
        self.id = id
        self.url = self.mpd = None
        self.marked = None

    def mark_download_succeeded(self):
        self.marked = "succeeded"

    def mark_download_failed(self):
        self.marked = "failed"

    def mark_download_skipped(self):
        self.marked = "skipped"


async def _noop(*a, **k):
    return None


def test_an_item_with_no_link_fails_with_a_plain_reason(monkeypatch):
    common_globals.set_up_contexvars()
    for name in COUNTERS:
        monkeypatch.setattr(common_globals, name, 0, raising=False)
    calls = []

    class _Recorder:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, a[0] if a else None))

    monkeypatch.setattr(common_globals, "log", _Recorder(), raising=False)
    monkeypatch.setattr(
        run_mod, "progress_updater",
        SimpleNamespace(download=SimpleNamespace(update_overall_task=lambda *a, **k: None)),
    )
    monkeypatch.setattr(run_mod, "desc", "{mediacount}")
    monkeypatch.setattr(run_mod, "log_download_progress", lambda *a: None)
    monkeypatch.setattr(
        run_mod, "asyncio",
        SimpleNamespace(sleep=_noop, CancelledError=asyncio.CancelledError),
    )
    monkeypatch.setattr(run_mod.fansly_video, "uses_stream", lambda ele: False)
    monkeypatch.setattr(run_mod, "get_medialog", lambda ele: "media")
    stop.clear()
    item = Item(1)
    results = []

    async def go():
        await run_mod.consumer(
            [(None, item, 1, "a")], None, [item], asyncio.Lock(),
            on_result=lambda ele, r: results.append(r),
        )

    try:
        asyncio.run(go())
    finally:
        stop.clear()
    assert results == ["failed"] and item.marked == "failed"
    assert common_globals.skipped == 1
    assert ("info", "media Not downloaded: it has no link (locked or removed)") in calls
    assert not [name for name, _ in calls if name == "traceback_"]
