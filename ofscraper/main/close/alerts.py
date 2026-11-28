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
# the multi-profile parent's alerts, one set per profile it runs
_failing_by_profile = {}
_loaded = False
# kinds this process reported failing, announced or already open
_raised = set()


def _ensure_loaded_locked():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        import ofscraper.main.close.status_file as status_file

        _failing.update(status_file.read_failing_alerts())
        for profile, kinds in status_file.read_profile_alerts().items():
            _failing_by_profile.setdefault(profile, set()).update(kinds)
    except Exception as e:
        log.debug(f"alert state not loaded from status file: {e}")


def _kinds_locked(profile):
    return _failing if profile is None else _failing_by_profile.setdefault(profile, set())


def _snapshot_locked():
    return set(_failing), {p: set(k) for p, k in _failing_by_profile.items() if k}


def _save_state(snapshot):
    kinds, by_profile = snapshot
    try:
        import ofscraper.main.close.status_file as status_file

        status_file.set_failing_alerts(kinds, by_profile=by_profile)
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


def _send(kind, message, profile=None):
    s = settings.get_settings()
    site, active = _site_and_profile()
    profile = profile or active
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
        import ofscraper.utils.of_env.of_env as env
        from ofscraper.utils.system.subprocess import run

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


def _announce(kind, message, profile):
    if profile is None:
        _send(kind, message)
    else:
        _send(kind, message, profile=profile)


def failing(kind, message, profile=None):
    """Announce that kind has started failing; quiet while it stays failing.
    profile: the multi-profile parent's alert for that profile's runs."""
    with _lock:
        _ensure_loaded_locked()
        if profile is None:
            _raised.add(kind)
        kinds = _kinds_locked(profile)
        if kind in kinds:
            return False
        kinds.add(kind)
        snapshot = _snapshot_locked()
    _save_state(snapshot)
    _announce(kind, message, profile)
    return True


def recovered(kind, message, profile=None):
    """Announce that kind works again, if it was failing."""
    with _lock:
        _ensure_loaded_locked()
        kinds = _kinds_locked(profile)
        if kind not in kinds:
            return False
        kinds.discard(kind)
        snapshot = _snapshot_locked()
    _save_state(snapshot)
    _announce(kind, message, profile)
    return True


def after_pass(outcome, profile=None):
    """A daemon pass ended with this exit status: announce a pass that fails
    after good ones, and the first good one after failures. profile: one
    profile's run in a multi-profile pass, which has its own alert."""
    import ofscraper.main.close.exit_status as exit_status

    if outcome in (exit_status.OK, exit_status.PARTIAL):
        recovered(DAEMON_PASS, "Daemon passes are finishing again", profile=profile)
        # a pass the limit stopped ends as partial: recovered only once
        # there's room again (a profile's child keeps its own disk alert)
        if profile is None and _disk_alert_open() and _has_free_space():
            recovered(DISK_FULL, "Downloads are running again after the free-space limit")
    elif outcome != exit_status.AUTH:  # the login alert went out already
        failing(
            DAEMON_PASS, f"A daemon pass failed ({exit_status.label(outcome)}); see the log", profile=profile
        )


def after_run():
    """A one-off run ended well, a --profiles child's included: the
    free-space alert an earlier run of this profile raised is announced as
    recovered once this run didn't reach the limit and there's room again.
    Left to a daemon that owns the status file (a run beside it)."""
    import ofscraper.main.close.status_file as status_file

    if (
        DISK_FULL in current()
        and DISK_FULL not in _raised
        and not status_file.owned_by_live_daemon()
        and _has_free_space()
    ):
        recovered(DISK_FULL, "Downloads are running again after the free-space limit")


def _disk_alert_open():
    with _lock:
        return DISK_FULL in _failing


def _has_free_space():
    try:
        import ofscraper.utils.system.free as free

        # every disk downloads go to: an alert one type_options disk raised
        # isn't over while that disk is still full
        return free.check_every_disk()
    except Exception as e:
        log.debug(f"free space not checked: {e}")
        return False


def current(profile=None):
    """The kinds failing now (for one profile of the multi-profile parent)."""
    with _lock:
        _ensure_loaded_locked()
        return set(_kinds_locked(profile))


def reset(reload=False):
    global _loaded
    with _lock:
        _failing.clear()
        _failing_by_profile.clear()
        _raised.clear()
        _loaded = not reload
