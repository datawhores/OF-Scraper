"""Cleanup when a run stops: scraper.main, the daemon, and run_async.run."""

import asyncio
import contextlib
import queue
import signal
from types import SimpleNamespace

import pytest

import ofscraper.commands.scraper.scraper as scraper
from ofscraper.utils.context import run_async


@pytest.fixture
def main_run(monkeypatch):
    """scraper.main with its steps stubbed; returns the cleanups it ran."""
    cleaned = []
    monkeypatch.setattr(
        scraper.progress_utils,
        "stop_live_screen",
        lambda **kwargs: contextlib.nullcontext(),
    )
    monkeypatch.setattr(scraper, "print_start", lambda: None)
    monkeypatch.setattr(scraper.network, "check_cdm", lambda: None)
    monkeypatch.setattr(scraper.paths, "temp_cleanup", lambda: cleaned.append("temp"))
    monkeypatch.setattr(scraper.paths, "cleanDB", lambda: cleaned.append("db"))
    monkeypatch.setattr(
        scraper, "log", SimpleNamespace(traceback_=lambda *args: None)
    )
    return cleaned


def test_main_cleans_up_after_ctrl_c(main_run, monkeypatch):
    def scrapper():
        raise KeyboardInterrupt

    monkeypatch.setattr(scraper, "scrapper", scrapper)
    with pytest.raises(KeyboardInterrupt):
        scraper.main()
    # once before the run, once after the interrupt
    assert main_run == ["temp", "db", "temp", "db"]


def test_main_cleans_up_after_an_error(main_run, monkeypatch):
    def scrapper():
        raise ValueError("the run failed")

    monkeypatch.setattr(scraper, "scrapper", scrapper)
    with pytest.raises(ValueError, match="the run failed"):
        scraper.main()
    assert main_run == ["temp", "db", "temp", "db"]


def test_ctrl_c_during_error_cleanup_finishes_it_and_reports_the_error(
    main_run, monkeypatch
):
    def scrapper():
        raise ValueError("the run failed")

    def clean_db():
        main_run.append("db")
        if main_run.count("db") == 2:  # the cleanup after the error
            signal.raise_signal(signal.SIGINT)
            main_run.append("db finished")

    monkeypatch.setattr(scraper, "scrapper", scrapper)
    monkeypatch.setattr(scraper.paths, "cleanDB", clean_db)
    with pytest.raises(ValueError, match="the run failed"):
        scraper.main()
    assert main_run[-1] == "db finished"


class _InterruptWhenIdle(queue.Queue):
    def get(self, *args, **kwargs):
        if self.empty():
            raise KeyboardInterrupt
        return super().get(*args, **kwargs)


def _stub_daemon(monkeypatch, jobs, runner):
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: None)
    monkeypatch.setattr(
        scraper, "scraperManager", lambda: SimpleNamespace(runner=runner)
    )
    monkeypatch.setattr(
        scraper.settings, "get_settings", lambda: SimpleNamespace(output_level="NORMAL")
    )
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(sync_models=lambda: None)),
    )
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(scraper, "set_schedule", lambda *args, **kwargs: None)


def test_ctrl_c_during_daemon_cleanup_still_stops_with_the_original_interrupt(
    monkeypatch,
):
    cleared = []

    def clear():
        cleared.append(True)
        signal.raise_signal(signal.SIGINT)  # a second Ctrl+C while stopping

    monkeypatch.setattr(scraper.schedule, "clear", clear)
    jobs = _InterruptWhenIdle()
    _stub_daemon(monkeypatch, jobs, lambda: None)
    with pytest.raises(KeyboardInterrupt):
        scraper.daemon_process()
    assert cleared
    assert jobs.unfinished_tasks == 0


def test_daemon_error_is_raised_after_cleanup(monkeypatch):
    cleared = []
    monkeypatch.setattr(scraper.schedule, "clear", lambda: cleared.append(True))

    class FailingQueue(queue.Queue):
        def get(self, *args, **kwargs):
            raise OSError("queue broke")

    _stub_daemon(monkeypatch, FailingQueue(), lambda: None)
    with pytest.raises(OSError, match="queue broke"):
        scraper.daemon_process()
    assert cleared == [True]


def test_run_async_returns_the_result_and_passes_ctrl_c_on():
    @run_async.run
    async def answer():
        return 42

    @run_async.run
    async def interrupted():
        await asyncio.sleep(0)
        raise KeyboardInterrupt

    assert answer() == 42
    with pytest.raises(KeyboardInterrupt):
        interrupted()
