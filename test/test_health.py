"""Tests for ``ofscraper health`` (ofscraper/commands/health.py)."""

from datetime import datetime, timedelta, timezone
import json
import os
import pathlib

import pytest

import ofscraper.commands.health as health

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 23, 18, 0, 0, tzinfo=timezone.utc)


def _iso(delta_minutes=0):
    return (NOW + timedelta(minutes=delta_minutes)).isoformat()


def test_missing_status_file_is_healthy(tmp_path):
    healthy, reason = health.check_file(tmp_path / "missing.json", now=NOW)
    assert healthy is True
    assert "no status file" in reason


def test_one_off_run_is_healthy_even_if_old_or_failed_auth():
    data = {
        "version": 1,
        "mode": "once",
        "state": "stopped",
        "heartbeat": _iso(-500),
        "auth": "failed",
    }
    healthy, reason = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is True
    assert "one-off" in reason


def test_running_daemon_with_fresh_heartbeat_is_healthy():
    data = {
        "version": 1,
        "mode": "daemon",
        "state": "running",
        "heartbeat": _iso(-15),
        "auth": "ok",
    }
    healthy, reason = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is True
    assert "running" in reason


def test_running_daemon_with_stale_heartbeat_is_unhealthy():
    data = {
        "version": 1,
        "mode": "daemon",
        "state": "running",
        "heartbeat": _iso(-90),
        "auth": "ok",
    }
    healthy, reason = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is False
    assert "heartbeat" in reason


def test_idle_daemon_within_schedule_is_healthy():
    data = {
        "version": 1,
        "mode": "daemon",
        "state": "idle",
        "heartbeat": _iso(-5),
        "next_pass_at": _iso(25),
        "auth": "ok",
    }
    healthy, reason = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is True
    assert "idle" in reason


def test_idle_daemon_with_overdue_next_pass_is_unhealthy():
    data = {
        "version": 1,
        "mode": "daemon",
        "state": "idle",
        "heartbeat": _iso(-120),
        "next_pass_at": _iso(-75),
        "auth": "ok",
    }
    healthy, reason = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is False
    assert "overdue" in reason


def test_failed_login_is_unhealthy():
    for payload in (
        {"version": 1, "mode": "daemon", "state": "idle", "auth": "failed"},
        {
            "version": 1,
            "mode": "daemon",
            "state": "idle",
            # auth "ok" after it would mean the login was checked again since
            "auth": "unknown",
            "last_pass": {"status": 3, "outcome": "failed"},
        },
        {
            "version": 1,
            "mode": "daemon",
            "state": "idle",
            "auth": "ok",
            "profiles": {"p1": {"status": 0}, "p2": {"status": 3}},
        },
    ):
        healthy, reason = health.evaluate(payload, max_quiet_minutes=60, now=NOW)
        assert healthy is False
        assert "login" in reason


def test_failed_last_pass_of_the_daemon_is_unhealthy(tmp_path, capsys):
    path = tmp_path / "status.json"
    base = {
        "version": 1,
        "mode": "daemon",
        "state": "idle",
        "heartbeat": datetime.now(timezone.utc).isoformat(),
        "next_pass_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
        "auth": "ok",
    }
    for status, label, healthy in ((1, "error", False), (5, "unavailable", False),
                                   (0, "ok", True), (4, "partial", True)):
        last_pass = {"status": status, "status_label": label, "outcome": "ok"}
        path.write_text(json.dumps({**base, "last_pass": last_pass}), encoding="utf-8")
        assert health.main([str(path)]) == (0 if healthy else 1)
        out = capsys.readouterr().out
        if not healthy:
            assert "last pass failed" in out and label in out


def test_daemon_restarted_after_a_stop_mid_pass_is_healthy(tmp_path, monkeypatch, capsys):
    # docker stop mid-pass records an interrupted last pass; the restarted
    # daemon carries it over while its first pass runs
    import ofscraper.main.close.status_file as status_file

    path = tmp_path / "status.json"
    monkeypatch.setenv("OFSC_STATUS_FILE", str(path))
    status_file.reset()
    try:
        status_file.start_pass(mode="daemon")
        status_file.finish_pass(
            {"status": 130, "status_label": "interrupted", "outcome": "stopped"},
            outcome="stopped",
        )
        status_file.stop_daemon()
        status_file.reset()  # a new process
        status_file.start_pass(mode="daemon")
        assert json.loads(path.read_text(encoding="utf-8"))["last_pass"]["status"] == 130
        assert health.main([str(path)]) == 0
        assert "healthy" in capsys.readouterr().out
    finally:
        status_file.reset()


def _now_iso(minutes=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def test_a_failed_pass_from_before_the_restart_is_not_judged(tmp_path, capsys):
    # health answers for the daemon running now: a pass (or a login) that
    # ended before it started says nothing about it
    path = tmp_path / "status.json"
    data = {
        "version": 1, "mode": "daemon", "started": _now_iso(-10),
        "state": "running", "heartbeat": _now_iso(-1), "next_pass_at": None,
        "auth": "failed", "auth_at": _now_iso(-30),
        "last_pass": {"status": 1, "status_label": "error", "outcome": "failed",
                      "finished": _now_iso(-30)},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert health.main([str(path)]) == 0
    assert "healthy: daemon running" in capsys.readouterr().out

    # until its first pass ends, the heartbeat still decides
    data["heartbeat"] = _now_iso(-90)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert health.main([str(path)]) == 1
    assert "heartbeat" in capsys.readouterr().out


def test_a_failed_pass_or_login_of_the_current_daemon_is_unhealthy(tmp_path, capsys):
    path = tmp_path / "status.json"
    base = {
        "version": 1, "mode": "daemon", "started": _now_iso(-60),
        "state": "idle", "heartbeat": _now_iso(-1), "next_pass_at": _now_iso(20),
        "auth": "ok", "auth_at": _now_iso(-59),
    }
    failed_pass = {"status": 1, "status_label": "error", "outcome": "failed",
                   "finished": _now_iso(-10)}
    path.write_text(json.dumps({**base, "last_pass": failed_pass}), encoding="utf-8")
    assert health.main([str(path)]) == 1
    assert "last pass failed (error)" in capsys.readouterr().out

    login = {"auth": "failed", "auth_at": _now_iso(-5)}
    path.write_text(json.dumps({**base, **login}), encoding="utf-8")
    assert health.main([str(path)]) == 1
    assert "failed login" in capsys.readouterr().out


def test_a_one_off_run_is_still_healthy_with_a_failed_pass(tmp_path, capsys):
    path = tmp_path / "status.json"
    data = {
        "version": 1, "mode": "once", "started": _now_iso(-10), "state": "stopped",
        "heartbeat": _now_iso(-5), "auth": "failed", "auth_at": _now_iso(-6),
        "last_pass": {"status": 1, "status_label": "error", "outcome": "failed",
                      "finished": _now_iso(-5)},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    assert health.main([str(path)]) == 0
    assert "one-off" in capsys.readouterr().out


def test_unknown_extra_keys_are_ignored():
    data = {
        "version": 99,
        "mode": "daemon",
        "state": "running",
        "heartbeat": _iso(-5),
        "auth": "ok",
        "future_field": {"nested": [1, 2, 3]},
        "another_unknown": True,
    }
    healthy, _ = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is True


def test_invalid_json_is_unhealthy(tmp_path):
    bad = tmp_path / "status.json"
    bad.write_text("{not json", encoding="utf-8")
    healthy, reason = health.check_file(bad, now=NOW)
    assert healthy is False
    assert "could not read" in reason


def test_cli_reads_arg_and_env_and_exits_0_or_1(tmp_path, monkeypatch, capsys):
    path = tmp_path / "status.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "mode": "daemon",
                "state": "running",
                "heartbeat": datetime.now(timezone.utc).isoformat(),
                "auth": "ok",
            }
        ),
        encoding="utf-8",
    )
    assert health.main([str(path)]) == 0
    assert "healthy" in capsys.readouterr().out

    # Now mark login failed and read via OFSC_STATUS_FILE
    path.write_text(
        json.dumps({"version": 1, "mode": "daemon", "state": "idle", "auth": "failed"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OFSC_STATUS_FILE", str(path))
    assert health.main([]) == 1
    assert "unhealthy" in capsys.readouterr().out


def test_dockerfile_sets_status_file_env_and_healthcheck():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ENV OFSC_STATUS_FILE=" in dockerfile
    assert "HEALTHCHECK CMD ofscraper health" in dockerfile


# --- review follow-up ---------------------------------------------------------


def test_recovered_login_is_healthy_while_the_next_pass_runs():
    data = {
        "mode": "daemon", "state": "running", "heartbeat": _iso(-1), "auth": "ok",
        "last_pass": {"status": 3},  # the pass before the login was fixed
    }
    healthy, _ = health.evaluate(data, now=NOW)
    assert healthy is True


def test_idle_daemon_with_no_next_pass_goes_stale():
    data = {"mode": "daemon", "state": "idle", "next_pass_at": None, "auth": "ok"}
    data["heartbeat"] = _iso(-5)
    assert health.evaluate(data, max_quiet_minutes=60, now=NOW)[0] is True
    data["heartbeat"] = _iso(-120)
    healthy, reason = health.evaluate(data, max_quiet_minutes=60, now=NOW)
    assert healthy is False and "heartbeat" in reason


@pytest.mark.parametrize("value", ["-5", "nan", "inf", "0"])
def test_max_quiet_must_be_a_positive_number(value, capsys):
    with pytest.raises(SystemExit) as exc:
        health.main(["--max-quiet", value])
    assert exc.value.code == 2


def test_default_path_follows_main_profile_in_config(tmp_path, monkeypatch):
    monkeypatch.delenv("OFSC_STATUS_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # the home folder on Windows
    monkeypatch.delenv("OFSC_CONFIG_DIR", raising=False)
    config_home = tmp_path / ".config" / "ofscraper"
    config_home.mkdir(parents=True)
    (config_home / "config.json").write_text(json.dumps({"main_profile": "other"}), encoding="utf-8")
    assert health.default_status_path() == config_home / "other_profile" / "status.json"


# --- second review round -------------------------------------------------------


def _status_files(tmp_path, monkeypatch):
    monkeypatch.delenv("OFSC_STATUS_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # the home folder on Windows
    monkeypatch.delenv("OFSC_CONFIG_DIR", raising=False)
    config_home = tmp_path / ".config" / "ofscraper"
    (config_home / "main_profile").mkdir(parents=True)
    return config_home / "status.json", config_home / "main_profile" / "status.json"


def test_default_path_prefers_the_running_daemon_over_a_newer_one_off(tmp_path, monkeypatch):
    # the multi-profile parent, and main_profile's child writing its own file
    parent, child = _status_files(tmp_path, monkeypatch)
    parent.write_text(json.dumps({"mode": "daemon", "state": "running"}), encoding="utf-8")
    child.write_text(json.dumps({"mode": "once", "state": "running"}), encoding="utf-8")
    os.utime(parent, (1_000_000, 1_000_000))
    assert health.default_status_path() == parent


def test_default_path_takes_the_newer_file_when_neither_is_a_running_daemon(tmp_path, monkeypatch):
    parent, child = _status_files(tmp_path, monkeypatch)
    parent.write_text(json.dumps({"mode": "daemon", "state": "stopped"}), encoding="utf-8")
    child.write_text(json.dumps({"mode": "once", "state": "stopped"}), encoding="utf-8")
    os.utime(parent, (1_000_000, 1_000_000))
    assert health.default_status_path() == child
    os.utime(child, (500_000, 500_000))
    assert health.default_status_path() == parent


def test_idle_daemon_with_no_heartbeat_says_idle():
    data = {"mode": "daemon", "state": "idle", "next_pass_at": None, "auth": "ok"}
    healthy, reason = health.evaluate(data, now=NOW)
    assert healthy is False and reason == "unhealthy: daemon is idle with no valid heartbeat"
