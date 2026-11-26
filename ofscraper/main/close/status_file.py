"""Unattended-run status file (``status.json``).

Records the current state of a daemon or one-off run so a health check or
dashboard can tell a working run from a stuck or failed one. Written
atomically via a temporary file and ``os.replace``. Never includes creator
usernames.
"""

from datetime import datetime, timezone
import json
import logging
import os
import pathlib
import tempfile
import threading
import time

log = logging.getLogger("shared")

STATUS_ENV = "OFSC_STATUS_FILE"
VERSION = 1
HEARTBEAT_INTERVAL = 60.0

_lock = threading.Lock()
_mode = None  # "daemon" | "once" | None (auto-detect from settings)
_state = "stopped"
_auth = "unknown"
_auth_at = None  # when _auth was last recorded, so health can ignore a carried-over one
_started = None  # when this daemon (or run) started
_next_pass_at = None
_last_pass = None
_last_success = None
_failing_alerts = []
_last_heartbeat = None
_last_heartbeat_mono = 0.0
_loaded_from = None
_path_override = None  # the multi-profile parent's file
_custom = None  # the last payload write_custom wrote


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def status_path():
    """Path to the status file: ``OFSC_STATUS_FILE`` if set, else ``status.json``
    in the active profile folder. Returns ``None`` if neither can be resolved."""
    if _path_override is not None:
        return pathlib.Path(_path_override)
    override = (os.getenv("OFSC_STATUS_FILE") or "").strip()
    if override:
        return pathlib.Path(override)
    try:
        import ofscraper.utils.paths.common as common_paths

        return common_paths.get_profile_path() / "status.json"
    except Exception as e:
        log.debug(f"status file path not resolved: {e}")
        return None


def _read_existing(path):
    """Read an existing status file if present and valid JSON dict."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except FileNotFoundError:
        return None
    except Exception as e:
        log.debug(f"status file not read ({path}): {e}")
        return None


def _ensure_loaded_locked(path):
    """Carry over ``last_success``, ``last_pass``, ``auth`` and ``failing_alerts``
    from an existing file on disk once per target path."""
    global _loaded_from, _last_success, _last_pass, _auth, _auth_at, _failing_alerts
    if path is None or _loaded_from == path:
        return
    _loaded_from = path
    existing = _read_existing(path)
    if not existing:
        return
    if _last_success is None and isinstance(existing.get("last_success"), str):
        _last_success = existing["last_success"]
    if _last_pass is None and isinstance(existing.get("last_pass"), dict):
        _last_pass = existing["last_pass"]
    if _auth == "unknown" and existing.get("auth") in ("ok", "failed", "unknown"):
        _auth = existing["auth"]
        auth_at = existing.get("auth_at")
        _auth_at = auth_at if isinstance(auth_at, str) else None
    if not _failing_alerts and isinstance(existing.get("failing_alerts"), list):
        _failing_alerts = sorted(
            k for k in existing["failing_alerts"] if isinstance(k, str)
        )


def _detect_mode():
    if _mode is not None:
        return _mode
    try:
        import ofscraper.utils.settings as settings

        return "daemon" if getattr(settings.get_settings(), "daemon", None) else "once"
    except Exception:
        return "once"


def _atomic_write(path, payload):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".status.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        # mkstemp makes it 0600: health may run as another user (a
        # monitoring script, Docker's HEALTHCHECK)
        try:
            os.chmod(tmp_name, 0o644)
        except OSError:
            pass
        # On Windows a concurrent reader can momentarily hold the target open.
        for attempt in range(5):
            try:
                os.replace(tmp_name, path)
                return True
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))
    except BaseException:  # a Ctrl+C mid-write leaves no .tmp behind
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return True


def _ensure_started_locked(now):
    """A run without set_mode("daemon") started at its first write."""
    global _started
    if _started is None:
        _started = now


def _set_auth_locked(value, now):
    global _auth, _auth_at
    _ensure_started_locked(now)
    _auth = value
    _auth_at = now


def _payload_locked(extra=None):
    heartbeat = _last_heartbeat or _now_iso()
    _ensure_started_locked(heartbeat)
    payload = {
        "version": VERSION,
        "pid": os.getpid(),
        "mode": _detect_mode(),
        "started": _started,
        "state": _state,
        "heartbeat": heartbeat,
        "next_pass_at": _next_pass_at,
        "auth": _auth,
        "auth_at": _auth_at,
        "last_pass": _last_pass,
        "last_success": _last_success,
    }
    if _failing_alerts:
        payload["failing_alerts"] = list(_failing_alerts)
    if extra:
        payload.update(extra)
    return payload


def _live_daemon_owns(existing):
    """Whether the file belongs to a daemon that is still running in another
    process: a one-off run beside it (docker compose exec) leaves it alone."""
    if not existing or existing.get("mode") != "daemon" or existing.get("state") == "stopped":
        return False
    pid = existing.get("pid")
    # JSON true is a bool, and so an int (1)
    if not isinstance(pid, int) or isinstance(pid, bool) or pid == os.getpid():
        return False
    try:
        import psutil

        return psutil.pid_exists(pid)
    except Exception:
        return False


def owned_by_live_daemon():
    """Whether this run's status file belongs to a daemon running beside it."""
    target = status_path()
    return target is not None and _live_daemon_owns(_read_existing(target))


def _write_locked(path=None, extra=None):
    target = pathlib.Path(path) if path is not None else status_path()
    if target is None:
        return None
    if _detect_mode() == "once" and _live_daemon_owns(_read_existing(target)):
        log.debug(f"status file left to the daemon running beside this run ({target})")
        return None
    _ensure_loaded_locked(target)
    payload = _payload_locked(extra=extra)
    try:
        _atomic_write(target, payload)
    except Exception as e:
        log.debug(f"status file write failed ({target}): {e}")
        return None
    return payload


def _strip_record(record):
    """Copy a plan 15 run record without per-creator lines (no usernames)."""
    if not isinstance(record, dict):
        return None
    return {k: v for k, v in record.items() if k != "per_creator"}


def _on_item_finished(**_kwargs):
    touch_heartbeat()


def set_path(path):
    """Write to path whatever OFSC_STATUS_FILE says (the multi-profile parent)."""
    global _path_override
    with _lock:
        _path_override = path


def set_mode(mode):
    """Explicitly set mode to ``"daemon"`` or ``"once"``. Setting ``"daemon"``
    records the daemon's start time."""
    global _mode, _started
    with _lock:
        _mode = mode
        if mode == "daemon":
            _started = _now_iso()


def set_auth(value):
    """Record auth state (``"ok"``, ``"failed"`` or ``"unknown"``) and write."""
    global _last_heartbeat, _last_heartbeat_mono
    if value not in ("ok", "failed", "unknown"):
        return None
    with _lock:
        now = _now_iso()
        _set_auth_locked(value, now)
        _last_heartbeat = now
        _last_heartbeat_mono = time.monotonic()
        return _write_locked()


def start_pass(mode=None):
    """Mark the start of a pass, subscribe to ``item_finished``, and write."""
    global _mode, _state, _next_pass_at, _last_heartbeat, _last_heartbeat_mono
    try:
        import ofscraper.utils.events as events

        events.subscribe("item_finished", _on_item_finished)
    except Exception as e:
        log.debug(f"status file event subscribe failed: {e}")
    with _lock:
        if mode is not None:
            _mode = mode
        _state = "running"
        _next_pass_at = None
        _last_heartbeat = _now_iso()
        _last_heartbeat_mono = time.monotonic()
        return _write_locked()


def touch_heartbeat(now_mono=None):
    """Refresh ``heartbeat`` at most once per ``HEARTBEAT_INTERVAL`` seconds."""
    global _last_heartbeat, _last_heartbeat_mono
    current = time.monotonic() if now_mono is None else now_mono
    with _lock:
        if _last_heartbeat_mono and (current - _last_heartbeat_mono) < HEARTBEAT_INTERVAL:
            return False
        _last_heartbeat = _now_iso()
        _last_heartbeat_mono = current
        _write_locked()
        return True


def finish_pass(record=None, outcome=None):
    """Record the end of a pass (from plan 15's run record) and write."""
    global _state, _auth, _last_pass, _last_success, _last_heartbeat, _last_heartbeat_mono
    try:
        import ofscraper.utils.events as events

        events.unsubscribe("item_finished", _on_item_finished)
    except Exception as e:
        log.debug(f"status file event unsubscribe failed: {e}")

    import ofscraper.main.close.exit_status as exit_status

    with _lock:
        now = _now_iso()
        mode = _detect_mode()
        _state = "idle" if mode == "daemon" else "stopped"
        stripped = _strip_record(record)
        if stripped is not None:
            _last_pass = stripped
            status = stripped.get("status")
            rec_outcome = stripped.get("outcome") or outcome
            if status == int(exit_status.AUTH):
                _set_auth_locked("failed", now)
            elif rec_outcome == "ok" and status in (
                int(exit_status.OK),
                int(exit_status.PARTIAL),
            ):
                _last_success = stripped.get("finished") or now
                if _auth == "unknown":
                    _set_auth_locked("ok", now)
        _last_heartbeat = now
        _last_heartbeat_mono = time.monotonic()
        return _write_locked()


def set_next_pass(when):
    """Record when the daemon's next pass is scheduled (a ``datetime`` or ISO string)."""
    global _state, _next_pass_at, _last_heartbeat, _last_heartbeat_mono
    if isinstance(when, datetime):
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        iso = when.astimezone(timezone.utc).isoformat()
    else:
        iso = when
    with _lock:
        _state = "idle"
        _next_pass_at = iso
        _last_heartbeat = _now_iso()
        _last_heartbeat_mono = time.monotonic()
        return _write_locked()


def stop_daemon():
    """Record that the daemon has stopped."""
    global _state, _next_pass_at, _last_heartbeat, _last_heartbeat_mono
    try:
        import ofscraper.utils.events as events

        events.unsubscribe("item_finished", _on_item_finished)
    except Exception:
        pass
    with _lock:
        _state = "stopped"
        _next_pass_at = None
        _last_heartbeat = _now_iso()
        _last_heartbeat_mono = time.monotonic()
        return _write_locked()


def write_custom(payload, path=None):
    """Atomically write an explicit status payload (used by multi-profile daemons)."""
    global _custom
    target = pathlib.Path(path) if path is not None else status_path()
    if target is None:
        return None
    _custom = (target, dict(payload))
    try:
        _atomic_write(target, payload)
    except Exception as e:
        log.debug(f"status file write failed ({target}): {e}")
        return None
    return payload


def read_failing_alerts():
    """Return the set of currently failing alert kinds stored on disk."""
    target = status_path()
    if target is None:
        return set()
    existing = _read_existing(target)
    if not existing:
        return set()
    items = existing.get("failing_alerts")
    if not isinstance(items, list):
        return set()
    return {k for k in items if isinstance(k, str)}


def read_profile_alerts():
    """The multi-profile parent's failing alert kinds, per profile, from the
    ``failing_alerts`` of each entry under ``profiles``."""
    target = status_path()
    existing = _read_existing(target) if target is not None else None
    profiles = existing.get("profiles") if existing else None
    if not isinstance(profiles, dict):
        return {}
    found = {}
    for name, entry in profiles.items():
        items = entry.get("failing_alerts") if isinstance(entry, dict) else None
        if isinstance(items, list):
            found[name] = {k for k in items if isinstance(k, str)}
    return found


def with_profile_alerts(profiles, by_profile):
    """profiles (name -> run result) with each profile's failing alert kinds
    in its entry, profiles that only have alerts included."""
    merged = {}
    for name in [*profiles, *(p for p in by_profile if p not in profiles)]:
        entry = {k: v for k, v in (profiles.get(name) or {}).items() if k != "failing_alerts"}
        kinds = sorted(by_profile.get(name) or ())
        if kinds:
            entry["failing_alerts"] = kinds
        if entry:
            merged[name] = entry
    return merged


def set_failing_alerts(kinds, by_profile=None):
    """Persist the set of currently failing alert kinds to the status file;
    by_profile, the multi-profile parent's per profile, goes in its file's
    profile entries."""
    global _failing_alerts
    with _lock:
        target = status_path()
        if target is None:
            return None
        _ensure_loaded_locked(target)
        _failing_alerts = sorted(k for k in kinds if isinstance(k, str))
        if _custom is not None and _custom[0] == target:
            # the multi-profile parent's file: keep its layout
            payload = {k: v for k, v in _custom[1].items() if k != "failing_alerts"}
            if _failing_alerts:
                payload["failing_alerts"] = list(_failing_alerts)
            payload["profiles"] = with_profile_alerts(payload.get("profiles") or {}, by_profile or {})
            custom = _custom
        else:
            return _write_locked(path=target)
    result = write_custom(payload, path=custom[0])
    return result


def reset():
    """Reset in-memory state (for tests)."""
    global _mode, _state, _auth, _auth_at, _started, _next_pass_at, _last_pass, _last_success
    global _failing_alerts, _last_heartbeat, _last_heartbeat_mono, _loaded_from
    global _path_override, _custom
    try:
        import ofscraper.utils.events as events

        events.unsubscribe("item_finished", _on_item_finished)
    except Exception:
        pass
    with _lock:
        _mode = None
        _state = "stopped"
        _auth = "unknown"
        _auth_at = None
        _started = None
        _next_pass_at = None
        _last_pass = None
        _last_success = None
        _failing_alerts = []
        _last_heartbeat = None
        _last_heartbeat_mono = 0.0
        _loaded_from = None
        _path_override = None
        _custom = None
