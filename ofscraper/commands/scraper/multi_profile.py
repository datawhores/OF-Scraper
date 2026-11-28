"""Multi-profile daemon (``--daemon N --profiles a,b``).

Runs one child process per profile, one after another, on each pass. The
parent only schedules, forwards stop signals to the running child, reads each
child's exit code, and writes a daemon-level status file.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import signal
import subprocess
import sys
import time

import ofscraper.commands.scraper.utils.schedule as daemon_schedule
import ofscraper.main.close.exit_status as exit_status
import ofscraper.main.close.status_file as status_file
import ofscraper.utils.context.exit as exit_context

log = logging.getLogger("shared")

_STRIP_VALUE_FLAGS = {
    "-d",
    "--daemon",
    "--daemon-jitter",
    "--profiles",
    "-r",
    "--profile",
}


def validate_multi_profile_args(params):
    """Validate ``--profiles`` combinations. Returns an error message or ``None``."""
    profiles = params.get("profiles") if isinstance(params, dict) else getattr(params, "profiles", None)
    if not profiles:
        return None
    daemon = params.get("daemon") if isinstance(params, dict) else getattr(params, "daemon", None)
    if not daemon:
        return "--profiles can only be used with --daemon."
    live_watch = (
        params.get("live_watch") if isinstance(params, dict) else getattr(params, "live_watch", False)
    )
    if live_watch:
        return "--live-watch cannot be used with --profiles."
    profile = params.get("profile") if isinstance(params, dict) else getattr(params, "profile", None)
    if profile:
        return "--profile cannot be combined with --profiles."
    return None


def _known_options():
    """Every option name of the main command, and how many values it takes
    (0 for a flag)."""
    try:
        import click

        from ofscraper.utils.args.parse.commands.main import program
    except Exception:
        return {}
    known = {}
    for param in program.params:
        if not isinstance(param, click.Option):
            continue
        takes = 0 if (param.is_flag or param.count) else param.nargs
        for opt in param.opts:
            known[opt] = takes
        for opt in param.secondary_opts:
            known[opt] = 0
    return known


def _strip_parent_flags(raw_argv, known=None):
    """Remove the daemon/profile options from ``raw_argv`` so a child runs
    once for one profile, reading it the way click does: an option's value is
    copied as it is, even when it starts with a dash (-u -draft), and
    -dc=LOW is the option -dc, not -d with the value c=LOW."""
    known = _known_options() if known is None else known
    cleaned = []
    items = list(raw_argv)
    i = 0
    while i < len(items):
        arg = items[i]
        if arg == "--" or not arg.startswith("-") or arg == "-":
            # the main command has no arguments or subcommands: click stops
            # reading options here, so neither does this
            cleaned.extend(items[i:])
            break
        name = arg.split("=", 1)[0] if "=" in arg else arg
        if name in known:
            # --opt value, --opt=value, -dc=LOW
            width = 1 if name != arg else 1 + known[name]
        elif not arg.startswith("--") and arg[:2] in known:
            # a short option with its value attached (-d30, -rfoo), or
            # short flags run together
            name, width = arg[:2], 1
        else:
            # not an option the parent knows: leave it to the child to reject
            name, width = None, 1
        chunk = items[i : i + width]
        if name not in _STRIP_VALUE_FLAGS:
            cleaned.extend(chunk)
        i += width
    return cleaned


def build_child_command(profile, raw_argv=None, executable=None, frozen=None):
    """Build the command line for one profile's one-off child process."""
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    exe = executable or sys.executable
    prefix = [exe] if is_frozen else [exe, "-m", "ofscraper"]
    argv = sys.argv[1:] if raw_argv is None else raw_argv
    # right after the program, so a "--" or a subcommand in argv
    # doesn't change how it's read
    return [*prefix, "--profile", profile, *_strip_parent_flags(argv)]


def _child_env(base_env=None):
    """Child environment without OFSC_STATUS_FILE so the child doesn't overwrite
    the parent's daemon-level status file."""
    env = dict(os.environ if base_env is None else base_env)
    env.pop("OFSC_STATUS_FILE", None)
    return env


def _label_for_code(returncode):
    try:
        return exit_status.label(returncode)
    except ValueError:
        return f"exit {returncode}"


def _terminal_ctrl_c_reached_child():
    """Whether a Ctrl+C typed in the terminal went to the child as well: the
    terminal sends it to every process of its foreground group (on Windows,
    to every process on the console)."""
    try:
        if sys.platform == "win32":
            return bool(sys.stdin) and sys.stdin.isatty()
        return os.tcgetpgrp(sys.stdin.fileno()) == os.getpgrp()
    except (AttributeError, OSError, ValueError):
        return False


def _stop_child(proc, timeout=30, forward=True):
    """Forward a stop signal to a running child and wait for it to exit.
    forward=False when the child got the signal already."""
    if proc.poll() is not None:
        return
    if forward:
        try:
            if sys.platform != "win32":
                proc.send_signal(signal.SIGINT)
            else:
                proc.terminate()
        except OSError:
            return
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except OSError:
            pass


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _overall_auth(results):
    if any(entry.get("auth") == "failed" for entry in results.values()):
        return "failed"
    if results and all(entry.get("auth") == "ok" for entry in results.values()):
        return "ok"
    return "unknown"


def daemon_status_path():
    """The parent's status file: OFSC_STATUS_FILE, else status.json in the
    config folder. Not a profile folder: a child writes its own profile's
    status.json there, main_profile's included."""
    override = (os.getenv(status_file.STATUS_ENV) or "").strip()
    if override:
        return override
    import ofscraper.utils.paths.common as common_paths

    return common_paths.get_config_home() / "status.json"


def _failing_alerts(profiles=()):
    """The parent's own failing alert kinds, and each profile's."""
    try:
        import ofscraper.main.close.alerts as alerts

        return sorted(alerts.current()), {p: alerts.current(profile=p) for p in profiles}
    except Exception:
        return [], {}


def _parse_iso(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _child_heartbeat(profile):
    """The heartbeat in a child's own status.json (its profile folder), which
    it moves on as it makes progress, or None."""
    try:
        import ofscraper.utils.paths.common as common_paths

        path = common_paths.get_profile_path(profile) / "status.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _parse_iso(data.get("heartbeat")) if isinstance(data, dict) else None


def _write_daemon_status(
    state, results, next_pass_at=None, last_success=None, heartbeat=None, started=None
):
    payload = {
        "version": status_file.VERSION,
        "pid": os.getpid(),
        "mode": "daemon",
        "started": started,
        "state": state,
        "heartbeat": heartbeat or _now_iso(),
        "next_pass_at": next_pass_at,
        "auth": _overall_auth(results),
        "last_success": last_success,
    }
    failing, by_profile = _failing_alerts(results)
    payload["profiles"] = status_file.with_profile_alerts(results, by_profile)
    if failing:
        payload["failing_alerts"] = failing
    status_file.write_custom(payload, path=daemon_status_path())
    return payload


def run_profiles_pass(
    profiles,
    raw_argv=None,
    popen=subprocess.Popen,
    results=None,
    last_success=None,
    stop_timeout=30,
    started=None,
):
    """Run one pass across ``profiles`` sequentially.

    Returns ``(results_dict, updated_last_success)``. A failing child does not
    stop the remaining profiles. Ctrl+C / SIGTERM is forwarded to the running
    child and re-raised. ``started`` is the daemon's start time, for health.
    """
    state_results = dict(results) if results else {}
    _write_daemon_status(
        "running", state_results, next_pass_at=None, last_success=last_success, started=started
    )

    all_ok = True
    for profile in profiles:
        cmd = build_child_command(profile, raw_argv=raw_argv)
        log.info(f"Daemon pass: starting profile '{profile}'")
        progress = _now_iso()
        _write_daemon_status(
            "running", state_results, next_pass_at=None, last_success=last_success,
            heartbeat=progress, started=started,
        )
        # no terminal input: a child that needs an answer (a rejected login's
        # Auth Menu) fails instead of waiting while the other profiles do
        proc = popen(cmd, env=_child_env(), stdin=subprocess.DEVNULL)
        try:
            while True:
                try:
                    returncode = proc.wait(timeout=status_file.HEARTBEAT_INTERVAL)
                    break
                except subprocess.TimeoutExpired:
                    # a pass can take hours: the heartbeat moves on only when
                    # the child's own does, so health sees a child that hangs
                    child = _child_heartbeat(profile)
                    if child is not None and child > _parse_iso(progress):
                        progress = child.astimezone(timezone.utc).isoformat()
                    _write_daemon_status(
                        "running", state_results, next_pass_at=None,
                        last_success=last_success, heartbeat=progress, started=started,
                    )
        except BaseException as exc:
            terminal_ctrl_c = (
                isinstance(exc, KeyboardInterrupt)
                and not isinstance(exc, exit_context.SigtermInterrupt)
                and _terminal_ctrl_c_reached_child()
            )
            _stop_child(proc, timeout=stop_timeout, forward=not terminal_ctrl_c)
            raise

        if returncode == int(exit_status.AUTH):
            auth_state = "failed"
        elif returncode in (int(exit_status.OK), int(exit_status.PARTIAL)):
            auth_state = "ok"
        else:
            # this run didn't get as far as the login: keep what was known
            auth_state = (state_results.get(profile) or {}).get("auth", "unknown")

        if returncode not in (int(exit_status.OK), int(exit_status.PARTIAL)):
            all_ok = False

        state_results[profile] = {
            "status": returncode,
            "status_label": _label_for_code(returncode),
            "auth": auth_state,
            "finished": _now_iso(),
        }
        if returncode != int(exit_status.OK):
            log.warning(
                f"Daemon pass for profile '{profile}' finished with status "
                f"{returncode} ({state_results[profile]['status_label']})"
            )
        else:
            log.info(f"Daemon pass for profile '{profile}' finished with status 0 (ok)")
        _write_daemon_status(
            "running", state_results, next_pass_at=None, last_success=last_success, started=started
        )

    if profiles and all_ok:
        last_success = _now_iso()
    return state_results, last_success


def _profile_outcome(results, profile):
    """A profile's child's exit code this pass, for its daemon_pass alert."""
    try:
        return exit_status.ExitCode((results.get(profile) or {}).get("status"))
    except ValueError:
        return exit_status.ERROR


def _sleep_until(target_dt, wakeup=None, sleep_fn=time.sleep):
    while True:
        if wakeup is not None and wakeup.state == "requested":
            wakeup.state = "busy"
            log.info("SIGUSR1 received while idle: starting the next daemon pass")
            return
        remaining = (target_dt - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return
        sleep_fn(min(remaining, 0.5))


def run_multi_profile_daemon(
    args,
    raw_argv=None,
    popen=subprocess.Popen,
    sleep_fn=time.sleep,
    max_passes=None,
):
    """Main scheduling loop for ``--daemon N --profiles a,b``."""
    error = validate_multi_profile_args(args)
    if error:
        raise SystemExit(exit_status.USAGE)

    exit_context.sigterm_as_keyboard_interrupt()
    profiles = list(args.profiles)
    interval = float(args.daemon)
    jitter = float(getattr(args, "daemon_jitter", 0) or 0)
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.install()
    # the alerts' state goes in the parent's file, not a profile's
    status_file.set_path(daemon_status_path())
    import ofscraper.main.close.alerts as alerts

    results = {}
    last_success = None
    started = _now_iso()
    passes = 0
    try:
        log.info(f"[bold]Daemon mode on (profiles: {', '.join(profiles)})[/bold]")
        while True:
            wakeup.state = "busy"
            results, last_success = run_profiles_pass(
                profiles,
                raw_argv=raw_argv,
                popen=popen,
                results=results,
                last_success=last_success,
                started=started,
            )
            passes += 1
            for profile in profiles:
                alerts.after_pass(_profile_outcome(results, profile), profile=profile)
            if max_passes is not None and passes >= max_passes:
                return results

            wait_minutes = daemon_schedule.next_wait_minutes(interval, jitter)
            next_dt = datetime.now(timezone.utc) + timedelta(minutes=wait_minutes)
            log.debug(f"Next multi-profile pass at ~ {next_dt.isoformat()}")
            _write_daemon_status(
                "idle",
                results,
                next_pass_at=next_dt.isoformat(),
                last_success=last_success,
                started=started,
            )
            wakeup.state = "idle"
            _sleep_until(next_dt, wakeup=wakeup, sleep_fn=sleep_fn)
    finally:
        wakeup.restore()
        _write_daemon_status(
            "stopped",
            results,
            next_pass_at=None,
            last_success=last_success,
            started=started,
        )
