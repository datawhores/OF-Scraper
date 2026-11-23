"""The state the downloads of a run share is a DownloadContext. The globals
module's names read and write the process's current context, so code and
tests that use common_globals.<name> see what a manager made without a
context of its own uses."""

import asyncio
from contextlib import closing
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.utils.globals import DownloadContext
import ofscraper.utils.settings as settings


class _ShutDown:
    """Shuts down a context's thread pool."""

    def __init__(self, ctx):
        self.ctx = ctx

    def close(self):
        if self.ctx.thread:
            self.ctx.thread.shutdown()


def test_module_names_read_and_write_the_current_context(monkeypatch):
    ctx = common_globals.current()
    monkeypatch.setattr(common_globals, "photo_count", 4)
    assert ctx.photo_count == 4
    common_globals.photo_count += 1
    assert ctx.photo_count == common_globals.photo_count == 5
    marker = object()
    monkeypatch.setattr(ctx, "log", marker)
    assert common_globals.log is marker


def test_a_patch_of_a_module_name_is_undone_on_the_context():
    ctx = common_globals.current()
    before = ctx.log
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(common_globals, "log", "patched", raising=False)
        assert ctx.log == "patched"
    assert ctx.log is before


def test_main_globals_resets_the_current_context_in_place(monkeypatch):
    monkeypatch.setattr(
        settings, "get_settings", lambda *a, **k: SimpleNamespace(download_sems=3)
    )
    log, console = object(), object()
    monkeypatch.setattr(common_globals.logger, "get_shared_logger", lambda **k: log)
    monkeypatch.setattr(common_globals.console_, "get_shared_console", lambda: console)
    ctx = common_globals.current()
    saved = dict(vars(ctx))
    try:
        ctx.photo_count = ctx.skipped = 7
        common_globals.mainProcessVariableInit()
        with closing(_ShutDown(ctx)):
            # the same object: a manager holding it sees the new run's state
            assert common_globals.current() is ctx
            assert (ctx.photo_count, ctx.skipped, ctx.total_bytes) == (0, 0, 0)
            assert ctx.sem._value == 3
            assert ctx.thread._max_workers == 6
            assert ctx.dirSet == set() and ctx.attempt.get() == 0
            assert common_globals.sem is ctx.sem
            assert (ctx.log, ctx.console) == (log, console)
    finally:
        vars(ctx).update(saved)


def test_a_new_context_starts_as_the_module_did():
    ctx = DownloadContext()
    assert ctx.log is None and ctx.attempt is None
    assert ctx.photo_count == ctx.total_bytes == ctx.stopped == 0
    assert ctx.sem is None and ctx.thread is None


def test_two_contexts_share_no_state():
    a = DownloadContext.for_run(2, log=object(), console=object())
    b = DownloadContext.for_run(2, log=object(), console=object())
    with closing(_ShutDown(a)), closing(_ShutDown(b)):
        for name in (
            "sem",
            "lock",
            "thread",
            "dirSet",
            "localDirSet",
            "fileHashes",
            "attempt",
            "attempt2",
        ):
            assert getattr(a, name) is not getattr(b, name), name
        assert common_globals.current() not in (a, b)

        a.photo_count += 2
        a.dirSet.add("x")
        assert b.photo_count == 0 and b.dirSet == set()

        async def go():
            a.attempt.set(5)
            await a.sem.acquire()
            return b.attempt.get(), b.sem._value, a.sem._value

        assert asyncio.run(go()) == (0, 2, 1)
