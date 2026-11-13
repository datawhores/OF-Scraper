import datetime
import queue
from types import SimpleNamespace

import pytest
import schedule

import ofscraper.commands.scraper.utils.schedule as daemon_schedule


def test_request_is_only_accepted_while_idle():
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.request(None, None)
    assert wakeup.state == "busy"
    wakeup.state = "idle"
    for _ in range(10):
        wakeup.request(None, None)
    assert wakeup.state == "requested"
    wakeup.state = "busy"
    wakeup.request(None, None)
    assert wakeup.state == "busy"


@pytest.mark.parametrize("trigger", ["signal", "timer", "both"])
def test_one_pass_and_fresh_interval_after_trigger(monkeypatch, trigger):
    scheduler = schedule.Scheduler()
    # Match the module API used by production code.
    scheduler.CancelJob = schedule.CancelJob
    jobs = queue.Queue()
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.installed = True
    monkeypatch.setattr(daemon_schedule, "schedule", scheduler)
    monkeypatch.setattr(daemon_schedule, "jobqueue", jobs)
    monkeypatch.setattr(daemon_schedule.settings, "get_settings", lambda: SimpleNamespace(daemon=60))
    monkeypatch.setattr(daemon_schedule.manager, "Manager", SimpleNamespace(
        current_model_manager=SimpleNamespace(sync_models=lambda: None)))
    def fail(error):
        raise error
    monkeypatch.setattr(daemon_schedule.log, "traceback_", fail, raising=False)
    steps = []
    runs = []

    def runner():
        runs.append("pass")

    def tick(delay):
        assert delay == 0.1
        steps.append(delay)
        if len(steps) == 1:
            assert wakeup.state == "idle" and jobs.empty()
            if trigger in ("timer", "both"):
                scheduler.jobs[0].next_run = datetime.datetime.now() - datetime.timedelta(seconds=5)
            if trigger in ("signal", "both"):
                for _ in range(5):
                    wakeup.request(None, None)
        elif len(steps) == 2:
            assert wakeup.state == "busy"
            assert not scheduler.jobs
            assert jobs.qsize() == 5  # four setup jobs, then the normal runner
            for _ in range(5):
                wakeup.request(None, None)
            while not jobs.empty():
                job = jobs.get_nowait()
                if job is runner:
                    job()
                jobs.task_done()
        else:
            assert len(steps) == 3
            assert runs == ["pass"] and jobs.empty()
            assert wakeup.state == "idle"
            assert len(scheduler.jobs) == 1
            assert scheduler.jobs[0].next_run > datetime.datetime.now() + datetime.timedelta(minutes=59)
            wakeup.stopped = True

    monkeypatch.setattr(daemon_schedule.time, "sleep", tick)
    daemon_schedule.set_schedule(runner, wakeup=wakeup)
    assert runs == ["pass"]


def test_install_and_restore_previous_handler(monkeypatch):
    previous = object()
    handlers = []
    monkeypatch.setattr(daemon_schedule.signal, "SIGUSR1", 12345, raising=False)
    def install(number, handler):
        handlers.append((number, handler))
        return previous
    monkeypatch.setattr(daemon_schedule.signal, "signal", install)
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.install()
    wakeup.restore()
    wakeup.restore()
    assert handlers == [(12345, wakeup.request), (12345, previous)]
    assert wakeup.stopped and not wakeup.installed


def test_platform_without_sigusr1_is_unchanged(monkeypatch):
    monkeypatch.delattr(daemon_schedule.signal, "SIGUSR1", raising=False)
    def unexpected(*args):
        raise AssertionError("must not register an unavailable signal")
    monkeypatch.setattr(daemon_schedule.signal, "signal", unexpected)
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.install()
    assert not wakeup.installed
    wakeup.restore()


@pytest.mark.skipif(not hasattr(daemon_schedule.signal, "SIGUSR1"), reason="Unix signals required")
@pytest.mark.parametrize("stop_signal", ["SIGTERM", "SIGINT"])
def test_real_daemon_signal_lifecycle(tmp_path, stop_signal):
    import os
    from pathlib import Path
    import signal
    import subprocess
    import sys
    import time

    repo = Path(__file__).resolve().parents[1]
    output = tmp_path / "probe.log"
    env = {**os.environ, "PYTHONPATH": str(repo), "HOME": str(tmp_path),
           "OFS_SIGNAL_PROBE_DIR": str(tmp_path)}
    with output.open("w") as stream:
        process = subprocess.Popen(
            [sys.executable, "-u", str(repo / "test/daemon_signal_probe.py")],
            cwd=repo, env=env, stdout=stream, stderr=stream,
        )
        def wait(marker):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                text = output.read_text()
                if marker in text:
                    return
                assert process.poll() is None, text
                time.sleep(0.02)
            pytest.fail(output.read_text())

        try:
            wait("START 1")
            process.send_signal(signal.SIGUSR1)  # ignored while active
            (tmp_path / "release-1").touch()
            wait("IDLE 1")
            time.sleep(0.3)
            assert "START 2" not in output.read_text()
            process.send_signal(signal.SIGUSR1)
            wait("START 2")
            for _ in range(100):
                process.send_signal(signal.SIGUSR1)
            (tmp_path / "release-2").touch()
            wait("IDLE 2")
            time.sleep(0.3)
            assert "START 3" not in output.read_text()
            process.send_signal(signal.SIGUSR1)
            wait("START 3")
            process.send_signal(getattr(signal, stop_signal))
            assert process.wait(timeout=10) == 0, output.read_text()
            assert "STOPPED" in output.read_text()
            assert "HANDLER_RESTORED True" in output.read_text()
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
