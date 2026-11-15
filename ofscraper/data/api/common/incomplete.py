"""Scans that stopped early must not be recorded as complete.

Timeline, archived, streams and messages scans start from a point worked out
from the database (the newest saved post, or the oldest one still to
download). The posts a scan did fetch are saved, so after a failed page that
point moves past posts that were never fetched, and later runs skip them.

A scan that loses a page says so with ``mark_incomplete``. ``save_scan``
then records where the scan started, and the next run of that area starts
there instead (``start_scan``). The record is cleared by ``commit_scan`` once
a later scan of the area finished and its posts were saved.
"""

import logging

import arrow

import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")

INCOMPLETE = "incomplete"
COMPLETE = "complete"

# (model_id, area) -> INCOMPLETE or COMPLETE for scans in this process
_scans = {}


def _state_key(model_id, api):
    return (model_id, api.lower())


def _cache_key(model_id, api):
    return f"{model_id}_incomplete_{api.lower()}_v2_scrape"


def _date(after):
    return arrow.get(after).format(of_env.getattr("API_DATE_FORMAT"))


def start_scan(model_id, api, after):
    """Begin a scan from ``after``, and return where to start instead.

    When an earlier scan of this area stopped early, start no later than
    where that one started. An explicit --after is kept as given.
    """
    _scans.pop(_state_key(model_id, api), None)
    if getattr(settings.get_settings(), "after", None) is not None:
        return after
    rescan = cache.get(_cache_key(model_id, api))
    if rescan is None or rescan >= after:
        return after
    log.info(f"{api}: the last scan stopped early, rescanning from {_date(rescan)}")
    return rescan


def mark_incomplete(model_id, api, reason):
    """A page of this scan wasn't fetched."""
    _scans[_state_key(model_id, api)] = INCOMPLETE
    log.warning(f"{api}: scan stopped early: {reason}")


def save_scan(model_id, api, after, username=None):
    """Finish a scan that started at ``after``. Returns True if it stopped early.

    An incomplete scan is recorded now, before its posts are saved, so the
    next run starts from ``after`` again.
    """
    key = _state_key(model_id, api)
    if _scans.get(key) != INCOMPLETE:
        _scans[key] = COMPLETE
        return False
    previous = cache.get(_cache_key(model_id, api))
    rescan = after if previous is None else min(previous, after)
    cache.set(_cache_key(model_id, api), rescan)
    log.warning(
        f"[{username}] {api} scan is incomplete: some pages weren't fetched. "
        f"The next run rescans from {_date(rescan)}"
    )
    return True


def commit_scan(model_id, api):
    """The area's posts are saved: a complete scan clears the rescan record."""
    if _scans.pop(_state_key(model_id, api), None) != COMPLETE:
        return
    if cache.get(_cache_key(model_id, api)) is not None:
        cache.set(_cache_key(model_id, api), None)
