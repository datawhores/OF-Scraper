"""Status file (main/close/status_file.py): pass state, heartbeat, atomic writes."""

import asyncio
import json
import os
import queue
import threading
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.scraper as scraper
import ofscraper.commands.utils.scrape_context as scrape_context
import ofscraper.main.close.alerts as alerts
import ofscraper.main.close.exit_status as exit_status
import ofscraper.main.close.final.run_record as run_record
import ofscraper.main.close.status_file as status_file
import ofscraper.utils.events as events
from ofscraper.managers.stats import StatsManager
from ofscraper.managers.utils.state import EActivity

DOWNLOAD = EActivity.ScrapeActivity.DOWNLOAD


def _sample_stats():
    stats = StatsManager()
    stats.update_stats(
        "secret_creator_name",
        DOWNLOAD,
        [
            SimpleNamespace(
                mediatype="Images",
                size=512,
                download_attempted=True,
                download_succeeded=True,
                download_stopped=False,
            )
        ],
    )
    return stats


class _FakeModels:
    def get_processed(self, activity):
        return {"secret_creator_name"} if activity == DOWNLOAD else set()

    def get_unprocessed(self, activity):
        return []


@pytest.fixture
def env_status(monkeypatch, tmp_path):
    """Point OFSC_STATUS_FILE at a fresh file and stub settings/managers."""
    path = tmp_path / "status.json"
    monkeypatch.setenv("OFSC_STATUS_FILE", str(path))
    state = SimpleNamespace(
        path=path,
        stats=_sample_stats(),
        models=_FakeModels(),
        settings=SimpleNamespace(
            site="onlyfans",
            command="scraper",
            discord_level="OFF",
            post_script=None,
            profile="main_profile",
            daemon=None,
        ),
    )
    monkeypatch.setattr(
        run_record,
        "manager",
        SimpleNamespace(
            Manager=SimpleNamespace(
                stats_manager=state.stats,
                current_model_manager=state.models,
            )
        ),
    )
    monkeypatch.setattr(run_record.settings, "get_settings", lambda: state.settings)
    import ofscraper.utils.settings as app_settings

    monkeypatch.setattr(app_settings, "get_settings", lambda: state.settings)
    import ofscraper.utils.profiles.data as profile_data

    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")
    status_file.reset()
    exit_status.reset()
    yield state
    status_file.reset()
    exit_status.reset()


def test_clean_pass_writes_status_without_usernames(env_status):
    with scrape_context.scrape_context_manager():
        running = json.loads(env_status.path.read_text(encoding="utf-8"))
        assert running["version"] == 1
        assert running["pid"] == os.getpid()
        assert running["mode"] == "once"
        assert running["state"] == "running"
        assert running["heartbeat"]
        assert running["next_pass_at"] is None
        run_record.finish("ok")

    raw = env_status.path.read_text(encoding="utf-8")
    assert "secret_creator_name" not in raw
    data = json.loads(raw)
    assert data["state"] == "stopped"
    assert data["auth"] == "ok"
    assert data["last_success"] == data["last_pass"]["finished"]
    assert data["last_pass"]["outcome"] == "ok"
    assert data["last_pass"]["status"] == 0
    assert "per_creator" not in data["last_pass"]
    assert data["last_pass"]["creators"] == {"done": 1, "failed": 0}
    assert data["last_pass"]["totals"]["downloads"]["photos"] == 1


def test_failed_pass_keeps_last_success_and_records_auth_failure(env_status):
    # First: a clean pass sets last_success
    with scrape_context.scrape_context_manager():
        run_record.finish("ok")
    first = json.loads(env_status.path.read_text(encoding="utf-8"))
    first_success = first["last_success"]
    assert first_success

    # Second: a failing pass with AUTH exit status
    exit_status.reset()
    with pytest.raises(RuntimeError, match="rejected"):
        with scrape_context.scrape_context_manager():
            exit_status.record(exit_status.AUTH)
            raise RuntimeError("rejected")

    after = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert after["last_pass"]["outcome"] == "failed"
    assert after["last_pass"]["status"] == int(exit_status.AUTH)
    assert after["auth"] == "failed"
    assert after["last_success"] == first_success


def test_stopped_daemon_writes_stopped_state(env_status, monkeypatch):
    env_status.settings.daemon = 15

    class InterruptWhenIdle(queue.Queue):
        def get(self, *args, **kwargs):
            if self.empty():
                raise KeyboardInterrupt
            return super().get(*args, **kwargs)

    jobs = InterruptWhenIdle()
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: status_file.set_auth("ok"))
    monkeypatch.setattr(
        scraper,
        "scraperManager",
        lambda: SimpleNamespace(runner=lambda: run_record.finish("ok")),
    )
    monkeypatch.setattr(
        scraper.settings,
        "get_settings",
        lambda: SimpleNamespace(output_level="NORMAL", daemon=15),
    )
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(sync_models=lambda: None)),
    )
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(scraper, "set_schedule", lambda *args, **kwargs: None)

    run_record.start()
    with pytest.raises(KeyboardInterrupt):
        scraper.daemon_process()

    data = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert data["mode"] == "daemon"
    assert data["state"] == "stopped"
    assert data["next_pass_at"] is None
    assert data["auth"] == "ok"


def test_heartbeat_refreshed_by_item_finished_at_most_once_per_minute(env_status, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(status_file.time, "monotonic", lambda: clock[0])

    times = iter(
        [
            "2026-11-23T18:00:00+00:00",
            "2026-11-23T18:01:05+00:00",
            "2026-11-23T18:02:10+00:00",
        ]
    )
    monkeypatch.setattr(status_file, "_now_iso", lambda: next(times))

    status_file.start_pass(mode="daemon")
    initial = json.loads(env_status.path.read_text(encoding="utf-8"))["heartbeat"]
    assert initial == "2026-11-23T18:00:00+00:00"

    # 30 seconds later: throttled, no write
    clock[0] = 1030.0
    asyncio.run(events.emit("item_finished", ele=None, username="u", result="downloaded", reason=None))
    assert json.loads(env_status.path.read_text(encoding="utf-8"))["heartbeat"] == initial

    # 65 seconds after start: refreshed
    clock[0] = 1065.0
    asyncio.run(events.emit("item_finished", ele=None, username="u", result="downloaded", reason=None))
    assert json.loads(env_status.path.read_text(encoding="utf-8"))["heartbeat"] == "2026-11-23T18:01:05+00:00"

    # 10 seconds later: throttled again
    clock[0] = 1075.0
    asyncio.run(events.emit("item_finished", ele=None, username="u", result="downloaded", reason=None))
    assert json.loads(env_status.path.read_text(encoding="utf-8"))["heartbeat"] == "2026-11-23T18:01:05+00:00"

    # After finish_pass, item_finished is unsubscribed
    status_file.finish_pass()
    clock[0] = 1200.0
    asyncio.run(events.emit("item_finished", ele=None, username="u", result="downloaded", reason=None))
    assert json.loads(env_status.path.read_text(encoding="utf-8"))["heartbeat"] == "2026-11-23T18:02:10+00:00"


def test_concurrent_reader_always_sees_complete_json(env_status):
    status_file.start_pass(mode="daemon")
    stop = threading.Event()
    errors = []
    reads = [0]

    def reader():
        while not stop.is_set():
            try:
                data = json.loads(env_status.path.read_text(encoding="utf-8"))
                assert data["version"] == 1
                reads[0] += 1
            except PermissionError:
                # Transient sharing violation on Windows while replacing is acceptable for a raw read
                continue
            except Exception as exc:
                errors.append(exc)
                return

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    try:
        for i in range(40):
            status_file.write_custom({"version": 1, "seq": i, "state": "running"})
    finally:
        stop.set()
        t.join(timeout=5)

    assert errors == []
    assert reads[0] > 0


def test_default_status_path_uses_profile_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("OFSC_STATUS_FILE", raising=False)
    import ofscraper.utils.paths.common as common_paths

    monkeypatch.setattr(common_paths, "get_profile_path", lambda: tmp_path / "main_profile")
    assert status_file.status_path() == tmp_path / "main_profile" / "status.json"


def test_alerts_state_persists_across_restarts(env_status, monkeypatch, tmp_path):
    script = tmp_path / "alert.py"
    script.write_text("", encoding="utf-8")
    s = SimpleNamespace(discord_level="OFF", alert_script=str(script), site="onlyfans")
    monkeypatch.setattr(alerts.settings, "get_settings", lambda: s)
    sent = []
    import ofscraper.utils.system.subprocess as subprocess_

    monkeypatch.setattr(subprocess_, "run", lambda cmd, input=None, **k: sent.append(json.loads(input)))

    alerts.reset()
    assert alerts.failing(alerts.LOGIN, "rejected")
    assert len(sent) == 1
    on_disk = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert on_disk["failing_alerts"] == ["login"]

    # Simulate a process restart: clear in-memory state and reload from status.json
    status_file.reset()
    alerts.reset(reload=True)
    assert not alerts.failing(alerts.LOGIN, "rejected again")
    assert len(sent) == 1

    assert alerts.recovered(alerts.LOGIN, "login works again")
    assert len(sent) == 2
    on_disk = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert "failing_alerts" not in on_disk


# --- review follow-up ---------------------------------------------------------


def test_a_one_off_run_leaves_a_running_daemons_file_alone(env_status):
    # docker compose exec ... ofscraper --action download, beside the daemon:
    # both see the image's OFSC_STATUS_FILE
    daemon = {
        "version": 1, "pid": os.getppid(), "mode": "daemon", "state": "idle",
        "heartbeat": "2026-11-24T10:00:00+00:00", "auth": "ok",
    }
    env_status.path.write_text(json.dumps(daemon), encoding="utf-8")
    with scrape_context.scrape_context_manager():
        run_record.finish("ok")
    assert json.loads(env_status.path.read_text(encoding="utf-8")) == daemon


def test_a_restarted_daemon_records_its_start_and_when_the_login_was_checked(env_status, monkeypatch):
    # health tells the current daemon's results from ones carried over from
    # before it started
    clock = iter(f"2026-11-24T10:{m:02d}:00+00:00" for m in range(60))
    monkeypatch.setattr(status_file, "_now_iso", lambda: next(clock))
    status_file.reset()
    status_file.set_mode("daemon")
    status_file.set_auth("failed")
    old = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert old["auth_at"] >= old["started"]

    status_file.reset()  # a new process
    status_file.set_mode("daemon")
    status_file.start_pass()
    carried = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert carried["started"] > old["started"]
    assert carried["auth"] == "failed" and carried["auth_at"] == old["auth_at"]

    status_file.set_auth("ok")
    checked = json.loads(env_status.path.read_text(encoding="utf-8"))
    assert checked["started"] == carried["started"]
    assert checked["auth_at"] > checked["started"]


def test_a_one_off_run_replaces_a_stopped_daemons_file(env_status):
    stopped = {"version": 1, "pid": os.getppid(), "mode": "daemon", "state": "stopped"}
    env_status.path.write_text(json.dumps(stopped), encoding="utf-8")
    with scrape_context.scrape_context_manager():
        run_record.finish("ok")
    assert json.loads(env_status.path.read_text(encoding="utf-8"))["mode"] == "once"


def test_a_true_pid_is_not_read_as_process_1(env_status):
    # JSON true is a bool, which Python counts as the int 1 (init, always
    # running): it isn't a daemon's PID
    daemon = {"version": 1, "pid": True, "mode": "daemon", "state": "idle"}
    env_status.path.write_text(json.dumps(daemon), encoding="utf-8")
    with scrape_context.scrape_context_manager():
        run_record.finish("ok")
    assert json.loads(env_status.path.read_text(encoding="utf-8"))["mode"] == "once"


def test_status_file_is_readable_by_others_and_no_temp_file_is_left(env_status, monkeypatch):
    status_file.set_auth("ok")
    if os.name != "nt":
        assert env_status.path.stat().st_mode & 0o777 == 0o644

    def interrupted(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(status_file.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        status_file._atomic_write(env_status.path, {"state": "running"})
    assert [p.name for p in env_status.path.parent.iterdir()] == ["status.json"]


def test_last_pass_error_is_redacted(env_status):
    with pytest.raises(RuntimeError):
        with scrape_context.scrape_context_manager():
            raise RuntimeError("failed with sess=abc123secret")
    raw = env_status.path.read_text(encoding="utf-8")
    assert "abc123secret" not in raw and "sess={sess}" in raw
