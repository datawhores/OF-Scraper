"""Alerts: a short message sent as soon as something needs a person.

An alert goes to Discord at any --discord level except OFF, and to
alert_script, which gets {"kind", "message", "site", "profile"} as JSON on
its input. Each kind is announced when it starts failing and again when it
recovers, not on every daemon pass.
"""

import json
import logging
import os
import threading

import ofscraper.utils.settings as settings

log = logging.getLogger("shared")

LOGIN = "login"
DISK_FULL = "disk_full"
DAEMON_PASS = "daemon_pass"

_lock = threading.Lock()
_failing = set()
_loaded = False


def _ensure_loaded_locked():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        import ofscraper.main.close.status_file as status_file

        _failing.update(status_file.read_failing_alerts())
    except Exception as e:
        log.debug(f"alert state not loaded from status file: {e}")


def _save_state(kinds):
    try:
        import ofscraper.main.close.status_file as status_file

        status_file.set_failing_alerts(kinds)
    except Exception as e:
        log.debug(f"alert state not saved to status file: {e}")


def _site_and_profile():
    s = settings.get_settings()
    try:
        import ofscraper.utils.profiles.data as profile_data

        profile = profile_data.get_active_profile()
    except Exception:
        profile = None
    return getattr(s, "site", None), profile


def _send(kind, message):
    s = settings.get_settings()
    site, profile = _site_and_profile()
    # the alert reaches Discord once, as the message below, not also as this line
    log.warning(f"Alert: {message}", extra={"skip_discord": True})
    if (getattr(s, "discord_level", None) or "OFF") != "OFF":
        try:
            from ofscraper.main.close.final.run_record import SITE_LABELS, send_discord

            label = SITE_LABELS.get(site, site or "OF-Scraper")
            send_discord(f"⚠️ {label}, {profile or 'profile'}: {message}")
        except Exception as e:
            log.debug(f"alert not sent to Discord: {e}")
    script = getattr(s, "alert_script", None)
    if not script:
        return
    if not os.path.exists(script):
        log.info(f"Alert script path is invalid: '{script}'")
        return
    try:
        from ofscraper.utils.system.subprocess import run
        import ofscraper.utils.of_env.of_env as env

        run(
            [script],
            input=json.dumps(
                {"kind": kind, "message": message, "site": site, "profile": profile},
                ensure_ascii=False,
            ),
            capture_output=True,
            text=True,
            check=True,
            level=env.getattr("FINAL_SCRIPT_SUBPROCESS_LEVEL"),
            name="Alert script",
            timeout=300,
        )
    except Exception as e:  # an alert must never break the run
        log.info(f"Alert script failed: {e}")


def failing(kind, message):
    """Announce that kind has started failing; quiet while it stays failing."""
    with _lock:
        _ensure_loaded_locked()
        if kind in _failing:
            return False
        _failing.add(kind)
        snapshot = set(_failing)
    _save_state(snapshot)
    _send(kind, message)
    return True


def recovered(kind, message):
    """Announce that kind works again, if it was failing."""
    with _lock:
        _ensure_loaded_locked()
        if kind not in _failing:
            return False
        _failing.discard(kind)
        snapshot = set(_failing)
    _save_state(snapshot)
    _send(kind, message)
    return True


def after_pass(outcome):
    """A daemon pass ended with this exit status: announce a pass that fails
    after good ones, and the first good one after failures."""
    import ofscraper.main.close.exit_status as exit_status

    if outcome in (exit_status.OK, exit_status.PARTIAL):
        recovered(DAEMON_PASS, "Daemon passes are finishing again")
        # a pass the limit stopped ends as partial: recovered only once
        # there's room again
        if _disk_alert_open() and _has_free_space():
            recovered(DISK_FULL, "Downloads are running again after the free-space limit")
    elif outcome != exit_status.AUTH:  # the login alert went out already
        failing(DAEMON_PASS, f"A daemon pass failed ({exit_status.label(outcome)}); see the log")


def _disk_alert_open():
    with _lock:
        return DISK_FULL in _failing


def _has_free_space():
    try:
        import ofscraper.utils.system.free as free

        return free.check_free_size()
    except Exception as e:
        log.debug(f"free space not checked: {e}")
        return False


def current():
    """The kinds failing now."""
    with _lock:
        _ensure_loaded_locked()
        return set(_failing)


def reset(reload=False):
    global _loaded
    with _lock:
        _failing.clear()
        _loaded = not reload
