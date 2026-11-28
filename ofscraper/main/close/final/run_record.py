"""One record of what a run (or a daemon pass) did, built once at its end.

The same record goes to ``post_script`` (as its ``summary`` key) and, with
``--discord SUMMARY``, to Discord as one message.
"""

import logging
from datetime import datetime, timezone

from humanfriendly import format_size

import ofscraper.managers.manager as manager
import ofscraper.utils.settings as settings
from ofscraper.managers.utils.state import EActivity, _get_all_enum_members

log = logging.getLogger("shared")

SITE_LABELS = {"onlyfans": "OnlyFans", "fansly": "Fansly"}
# Discord allows 2000 characters a message; the handler splits at 1500
MESSAGE_LIMIT = 1500
# the error a failed run's record carries, as characters
ERROR_LIMIT = 500

_started = None
_record = None


def start():
    """Mark the start of a run or daemon pass."""
    global _started, _record
    _started = datetime.now(timezone.utc)
    _record = None


def current():
    """The record of the run that has ended, or None before it ends."""
    return _record


def _creators():
    """How many queued creators were done, and how many weren't, across the
    run's activities. A creator done for one activity and not another counts
    as not done."""
    done, failed = set(), set()
    model_manager = manager.Manager.current_model_manager
    for activity in _get_all_enum_members(EActivity):
        try:
            done.update(model_manager.get_processed(activity))
            failed.update(model_manager.get_unprocessed(activity))
        except Exception:  # an activity this run never set up
            continue
    return {"done": len(done - failed), "failed": len(failed)}


def _safe_error(error):
    """The error as a log line shows it (cookies, tokens and signed links
    hidden), cut to ERROR_LIMIT: post_script gets it, not only the log."""
    import ofscraper.utils.logs.utils.sensitive as sensitive
    from ofscraper.utils.logs.classes.classes import SensitiveFormatter

    text = SensitiveFormatter()._filter(sensitive.hide_links(str(error)))
    return text if len(text) <= ERROR_LIMIT else text[: ERROR_LIMIT - 3] + "..."


def build(outcome="ok", error=None):
    """The run's record; ``outcome`` is "ok", "stopped" or "failed"."""
    s = settings.get_settings()
    totals = manager.Manager.stats_manager.totals(per_creator=True)
    per_creator = totals.pop("per_creator")
    try:
        import ofscraper.utils.profiles.data as profile_data

        profile = profile_data.get_active_profile()
    except Exception:
        profile = None
    try:
        creators = _creators()
    except Exception:
        creators = {"done": 0, "failed": 0}
    finished = datetime.now(timezone.utc)
    record = {
        "site": getattr(s, "site", None),
        "profile": profile,
        "command": getattr(s, "command", None),
        "started": _started.isoformat() if _started else None,
        "finished": finished.isoformat(),
        "outcome": outcome,
        "totals": totals,
        "creators": creators,
        "per_creator": per_creator,
    }
    if error:
        record["error"] = _safe_error(error)
    # plan 2's exit status so far: 0 ok, 4 partial, 3 login failed, ...
    import ofscraper.main.close.exit_status as exit_status

    status = exit_status.code()
    if outcome == "failed" and status == exit_status.OK:
        status = int(exit_status.ERROR)  # what the caller records next
    elif outcome == "stopped" and status == exit_status.OK:
        status = int(exit_status.INTERRUPTED)
    record["status"] = status
    record["status_label"] = exit_status.label(status)
    return record


def finish(outcome="ok", error=None):
    """Build the run's record once, send it to Discord at the SUMMARY level,
    and return it. A second call in the same run returns the first record."""
    global _record
    if _record is not None:
        return _record
    try:
        _record = build(outcome, error)
    except Exception as e:  # the summary must never break the run's end
        log.debug(f"run summary not built: {e}", exc_info=True)
        return None
    if getattr(settings.get_settings(), "discord_level", None) == "SUMMARY":
        send_discord(message(_record))
    try:
        import ofscraper.main.close.status_file as status_file

        status_file.finish_pass(_record, outcome=outcome)
    except Exception as e:
        log.debug(f"status file not updated at pass end: {e}")
    return _record


def _took(record):
    if not record.get("started"):
        return None
    seconds = (
        datetime.fromisoformat(record["finished"]) - datetime.fromisoformat(record["started"])
    ).total_seconds()
    minutes = round(seconds / 60)
    return f"{minutes} min" if minutes else f"{round(seconds)} s"


def message(record, limit=MESSAGE_LIMIT):
    """The record as one Discord message, cut to ``limit`` characters."""
    downloads = record["totals"]["downloads"]
    new_files = downloads["videos"] + downloads["audios"] + downloads["photos"]
    creators = record["creators"]
    site = SITE_LABELS.get(record.get("site"), record.get("site") or "OF-Scraper")
    head = f"{site}, {record.get('profile') or 'profile'}: "
    head += f"{creators['done'] + creators['failed']} creators, "
    head += f"{new_files} new files ({format_size(downloads['bytes'])}), "
    head += f"{downloads['failed']} failed."
    if creators["failed"]:
        head += f" {creators['failed']} creator{'s' if creators['failed'] != 1 else ''} not finished."
    if record["outcome"] == "failed":
        head += f" The run failed: {record.get('error') or 'see the log'} (exit status {record['status']})."
    elif record["outcome"] == "stopped":
        head += f" The run was stopped (exit status {record['status']})."
    took = _took(record)
    if took:
        head += f" Took {took}."
    lines = []
    for c in record["per_creator"]:
        if not c["new_files"]:
            continue
        line = f"- {c['username']}: {c['new_files']} new ({format_size(c['bytes'])})"
        if c["failed"]:
            line += f", {c['failed']} failed"
        lines.append(line)
    # one line per creator with new files, as many as fit
    def fits(shown):
        more = [f"... and {len(lines) - shown} more"] if shown < len(lines) else []
        return len("\n".join([head, *lines[:shown], *more])) <= limit

    shown = len(lines)
    while shown and not fits(shown):
        shown -= 1
    body = lines[:shown]
    if shown < len(lines):
        body.append(f"... and {len(lines) - shown} more")
    return "\n".join([head, *body])[:limit]


def send_discord(text):
    """Send text as one message through the Discord handler on the shared
    log, so it is redacted and retried like log lines."""
    from ofscraper.utils.logs.classes.handlers.discord import DiscordHandler

    for handler in logging.getLogger("shared").handlers:
        if isinstance(handler, DiscordHandler):
            handler.send_message(text)
            return True
    return False
