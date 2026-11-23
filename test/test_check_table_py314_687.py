"""#687: on Linux with Python 3.14, check table downloads failed with
"bad value(s) in fds_to_keep". Each download run made two unused
multiprocessing locks; with 3.14's forkserver start method a lock starts the
resource tracker, which passes sys.stderr.fileno() to the new process, and
inside the check table that's -1. A run's setup must make no multiprocessing
objects at all."""

import io
import multiprocessing.resource_tracker
import multiprocessing.synchronize
from contextlib import closing
from types import SimpleNamespace

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.settings as settings


class _NoFileStderr(io.StringIO):
    """Like the check table's captured stderr: no file behind it."""

    def fileno(self):
        return -1


def _refuse(*args, **kwargs):
    raise AssertionError("a download run made a multiprocessing object")


def test_download_run_setup_makes_no_multiprocessing_objects(monkeypatch):
    monkeypatch.setattr("sys.stderr", _NoFileStderr())
    # every multiprocessing lock, semaphore and condition is a SemLock, and
    # the resource tracker is what fails under forkserver and spawn
    monkeypatch.setattr(multiprocessing.synchronize.SemLock, "__init__", _refuse)
    monkeypatch.setattr(
        multiprocessing.resource_tracker._resource_tracker, "ensure_running", _refuse
    )
    monkeypatch.setattr(
        settings, "get_settings", lambda *a, **k: SimpleNamespace(download_sems=2)
    )
    monkeypatch.setattr(
        common_globals.logger, "get_shared_logger", lambda **k: object()
    )
    monkeypatch.setattr(common_globals.console_, "get_shared_console", lambda: object())
    ctx = common_globals.current()
    saved = dict(vars(ctx))
    try:
        common_globals.mainProcessVariableInit()
        with closing(SimpleNamespace(close=ctx.thread.shutdown)):
            assert ctx.sem._value == 2
    finally:
        vars(ctx).update(saved)
