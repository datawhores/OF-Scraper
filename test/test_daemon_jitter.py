"""Tests for ``--daemon-jitter`` in the daemon scheduler."""

from types import SimpleNamespace

import arrow
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.utils.schedule as daemon_schedule
import ofscraper.utils.args.parse.commands.main as main_cmd


def test_zero_jitter_gives_plain_interval():
    for _ in range(20):
        assert daemon_schedule.next_wait_minutes(30, 0) == 30
        assert daemon_schedule.next_wait_minutes(30, None) == 30


def test_nonzero_jitter_stays_inside_range():
    samples = [daemon_schedule.next_wait_minutes(15, 5) for _ in range(200)]
    assert all(15 <= value <= 20 for value in samples)
    assert len(set(samples)) > 1


def test_set_schedule_applies_jitter_to_next_pass(monkeypatch):
    # now: the pass is scheduled from it, and a past time would run at once
    fixed_now = arrow.utcnow().replace(microsecond=0)
    recorded = []
    wakeup = daemon_schedule.DaemonWakeup()

    class OnePassQueue:
        def __init__(self):
            self.calls = 0

        def join(self):
            self.calls += 1
            if self.calls > 1:
                wakeup.stopped = True

    monkeypatch.setattr(daemon_schedule, "jobqueue", OnePassQueue())
    monkeypatch.setattr(daemon_schedule.arrow, "now", lambda tz=None: fixed_now)
    monkeypatch.setattr(daemon_schedule.random, "uniform", lambda a, b: 4.0)
    monkeypatch.setattr(
        daemon_schedule.settings,
        "get_settings",
        lambda: SimpleNamespace(daemon=10.0, daemon_jitter=5.0),
    )
    monkeypatch.setattr(
        daemon_schedule.status_file, "set_next_pass", lambda dt: recorded.append(dt)
    )
    monkeypatch.setattr(
        daemon_schedule.time, "sleep", lambda _s: setattr(wakeup, "stopped", True)
    )

    try:
        daemon_schedule.set_schedule(lambda: None, wakeup=wakeup)
    finally:
        daemon_schedule.schedule.clear()

    assert len(recorded) == 1
    assert recorded[0] == fixed_now.shift(minutes=14).datetime


def test_cli_parses_daemon_jitter_and_rejects_negative():
    ctx = main_cmd.program.make_context("ofscraper", ["--daemon", "30", "--daemon-jitter", "5"])
    assert ctx.params["daemon"] == 30.0
    assert ctx.params["daemon_jitter"] == 5.0

    ctx_default = main_cmd.program.make_context("ofscraper", ["--daemon", "30"])
    assert ctx_default.params["daemon_jitter"] == 0.0

    with pytest.raises(Exception):
        main_cmd.program.make_context("ofscraper", ["--daemon", "30", "--daemon-jitter", "-1"])


def test_a_wait_over_a_day_isnt_wrapped_to_the_same_day(monkeypatch):
    # --daemon 1440 --daemon-jitter 30: the next pass is in 24.5 hours, not
    # at the same clock time later today
    fixed_now = arrow.now(daemon_schedule.tz.tzlocal()).replace(microsecond=0)
    wakeup = daemon_schedule.DaemonWakeup()
    scheduled = []

    class OnePassQueue:
        def join(self):
            pass

    def sleep(_s):
        scheduled.extend(job.next_run for job in daemon_schedule.schedule.jobs)
        wakeup.stopped = True

    monkeypatch.setattr(daemon_schedule, "jobqueue", OnePassQueue())
    monkeypatch.setattr(daemon_schedule.arrow, "now", lambda tz=None: fixed_now)
    monkeypatch.setattr(daemon_schedule.random, "uniform", lambda a, b: 30.0)
    monkeypatch.setattr(
        daemon_schedule.settings, "get_settings",
        lambda: SimpleNamespace(daemon=1440.0, daemon_jitter=30.0),
    )
    monkeypatch.setattr(daemon_schedule.status_file, "set_next_pass", lambda dt: None)
    monkeypatch.setattr(daemon_schedule.time, "sleep", sleep)
    try:
        daemon_schedule.set_schedule(lambda: None, wakeup=wakeup)
    finally:
        daemon_schedule.schedule.clear()
    assert scheduled == [fixed_now.shift(minutes=1470).naive]
