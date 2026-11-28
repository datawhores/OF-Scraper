"""Check whether an unattended OF-Scraper daemon is healthy from its status file.

Run as ``ofscraper health [STATUS_FILE] [--max-quiet MINUTES]``.
Starts without loading the scraper so Docker HEALTHCHECK and monitoring
scripts get an instant answer.
"""

import argparse
import json
import math
import os
import pathlib
import re
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_MAX_QUIET_MINUTES = 60
AUTH_EXIT_CODE = 3
OK_EXIT_CODES = (0, 4)  # ok, partial
INTERRUPTED_EXIT_CODE = 130  # Ctrl+C or SIGTERM


def _parse_iso(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _main_profile(config_home, paths):
    """The profile config.json names as main_profile, read without loading
    the app, as the profile folder's name."""
    from ofscraper.utils.of_env.values.main import load_main_config

    name = None
    try:
        data = json.loads((config_home / paths["configFile"]).read_text(encoding="utf-8-sig"))
        if isinstance(data.get("config"), dict):
            data = data["config"]
        name = data.get(paths["mainProfile"])
    except Exception:
        pass
    name = str(name or load_main_config()["PROFILE_DEFAULT"])
    return f"{re.sub('_profile', '', name)}_profile"


def _running_daemon(path):
    """Whether path is a daemon's file that doesn't say it has stopped."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(data, dict) and data.get("mode") == "daemon" and data.get("state") != "stopped"


def default_status_path():
    """OFSC_STATUS_FILE; else, of the multi-profile daemon's status.json in
    the config folder and the main profile's, a running daemon's, then the
    newer one: the main profile's one-off child doesn't hide its parent."""
    override = (os.getenv("OFSC_STATUS_FILE") or "").strip()
    if override:
        return pathlib.Path(override)
    # the environment defaults only, so the app isn't loaded
    from ofscraper.utils.of_env.values.path.files import load_file_paths_config

    paths = load_file_paths_config()
    config_home = pathlib.Path.home() / paths["configPath"]
    candidates = [
        config_home / "status.json",
        config_home / _main_profile(config_home, paths) / "status.json",
    ]
    found = [p for p in candidates if p.is_file()]
    if not found:
        return candidates[1]
    return max(found, key=lambda p: (_running_daemon(p), p.stat().st_mtime))


def _since_start(data, when):
    """Whether ``when`` is at or after the current daemon's start. A result
    from before it (carried over from the daemon that ran earlier) says
    nothing about the daemon running now. A file without "started" (written
    before it was recorded) is judged as a whole."""
    started = _parse_iso(data.get("started"))
    if started is None:
        return True
    at = _parse_iso(when)
    return at is not None and at >= started


def _current_last_pass(data):
    last_pass = data.get("last_pass")
    if isinstance(last_pass, dict) and _since_start(data, last_pass.get("finished")):
        return last_pass
    return None


def _login_failed(data):
    if data.get("auth") == "failed" and _since_start(data, data.get("auth_at")):
        return True
    last_pass = _current_last_pass(data)
    # auth "ok" is newer than the last pass: the login was checked again
    if (
        data.get("auth") != "ok"
        and isinstance(last_pass, dict)
        and last_pass.get("status") == AUTH_EXIT_CODE
    ):
        return True
    for entry in _current_profile_runs(data).values():
        if entry.get("auth") == "failed" or entry.get("status") == AUTH_EXIT_CODE:
            return True
    return False


def _current_profile_runs(data):
    """The --profiles daemon's profile entries whose run ended since it
    started."""
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    return {
        name: entry
        for name, entry in profiles.items()
        if isinstance(entry, dict) and _since_start(data, entry.get("finished"))
    }


def _failed_last_pass(data):
    """The label of the daemon's last pass when it ended neither ok nor
    partial, or None. A failed login is _login_failed's: a later login
    check can clear it. A pass stopped by Ctrl+C or docker stop didn't
    fail. A pass that ended before the current daemon started isn't
    judged: until its own first pass ends, the other checks decide."""
    last_pass = _current_last_pass(data)
    if not isinstance(last_pass, dict) or last_pass.get("outcome") == "stopped":
        return None
    status = last_pass.get("status")
    if (
        isinstance(status, int)
        and not isinstance(status, bool)
        and status not in (*OK_EXIT_CODES, AUTH_EXIT_CODE, INTERRUPTED_EXIT_CODE)
    ):
        return last_pass.get("status_label") or f"exit {status}"
    return None


def _failed_profile(data):
    """(name, label) of a multi-profile daemon's profile whose last run
    ended neither ok nor partial since the daemon started, or None."""
    for name, entry in _current_profile_runs(data).items():
        status = entry.get("status")
        if isinstance(status, int) and not isinstance(status, bool) and status not in OK_EXIT_CODES:
            return name, entry.get("status_label") or f"exit {status}"
    return None


def evaluate(data, max_quiet_minutes=DEFAULT_MAX_QUIET_MINUTES, now=None):
    """Return ``(healthy: bool, reason: str)`` for a parsed status dict."""
    if not isinstance(data, dict):
        return False, "unhealthy: status file is not a JSON object"

    mode = data.get("mode")
    if mode == "once":
        return True, "healthy: last run was a one-off"

    if _login_failed(data):
        return False, "unhealthy: last pass recorded a failed login"

    failed = _failed_last_pass(data)
    if failed:
        return False, f"unhealthy: the daemon's last pass failed ({failed})"

    failed = _failed_profile(data)
    if failed:
        return False, f"unhealthy: the last run of profile {failed[0]} failed ({failed[1]})"

    now_utc = (
        datetime.now(timezone.utc)
        if now is None
        else (now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc))
    )
    limit = timedelta(minutes=max_quiet_minutes)
    state = data.get("state")

    if state == "running" or (state == "idle" and data.get("next_pass_at") is None):
        # idle with no next pass is the moment between a pass and its
        # scheduling: as quiet as a running pass may be, no longer
        hb = _parse_iso(data.get("heartbeat"))
        if hb is None:
            return False, f"unhealthy: daemon is {state} with no valid heartbeat"
        age = now_utc - hb
        if age > limit:
            mins = int(age.total_seconds() // 60)
            return False, f"unhealthy: daemon heartbeat is {mins} min old (limit {max_quiet_minutes} min)"
        mins = max(0, int(age.total_seconds() // 60))
        return True, f"healthy: daemon {state} (heartbeat {mins} min ago)"

    if state == "idle":
        next_at = data.get("next_pass_at")
        if next_at is not None:
            parsed = _parse_iso(next_at)
            if parsed is None:
                return False, "unhealthy: daemon is idle with an invalid next_pass_at"
            overdue = now_utc - parsed
            if overdue > limit:
                mins = int(overdue.total_seconds() // 60)
                return False, f"unhealthy: daemon next pass overdue by {mins} min (limit {max_quiet_minutes} min)"
        return True, "healthy: daemon idle"

    if state == "stopped":
        return True, "healthy: daemon stopped"

    return True, f"healthy: state is {state or 'unknown'}"


def check_file(path, max_quiet_minutes=DEFAULT_MAX_QUIET_MINUTES, now=None):
    """Read ``path`` and return ``(healthy: bool, reason: str)``."""
    target = pathlib.Path(path)
    if not target.exists():
        return True, f"healthy: no status file at {target}"
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"unhealthy: could not read status file ({e})"
    return evaluate(data, max_quiet_minutes=max_quiet_minutes, now=now)


def _max_quiet(value):
    try:
        minutes = float(value)
    except ValueError:
        minutes = math.nan
    if not math.isfinite(minutes) or minutes <= 0:
        raise argparse.ArgumentTypeError(f"must be a number of minutes above 0, not {value!r}")
    return minutes


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ofscraper health",
        description="Check whether an unattended OF-Scraper daemon is healthy from its status file.",
    )
    parser.add_argument(
        "status_file",
        nargs="?",
        default=None,
        help="Path to the status JSON file (default: OFSC_STATUS_FILE, or of status.json in the config folder and in the main profile's folder, a running daemon's, then the newer one).",
    )
    parser.add_argument(
        "--max-quiet",
        type=_max_quiet,
        default=DEFAULT_MAX_QUIET_MINUTES,
        help=f"Minutes, above 0, before a quiet running daemon or overdue idle daemon counts as unhealthy (default: {DEFAULT_MAX_QUIET_MINUTES}).",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    target = pathlib.Path(args.status_file) if args.status_file else default_status_path()
    healthy, reason = check_file(target, max_quiet_minutes=args.max_quiet)
    print(reason)
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
