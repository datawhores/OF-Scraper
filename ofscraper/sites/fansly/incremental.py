"""Fansly repeat runs: stop scanning where the last finished scan began.

A Fansly run rescanned the creator's whole timeline and messages every time
unless ``--after`` was given, at the API's limit of about one call every
6 seconds. Pages come newest first, and Fansly post and message ids grow with
time (paging relies on it: ``before=<last id>``).

Each area keeps a mark in the profile cache: the newest post id its last
scan saw and the oldest one its last full scan saw, written only by a
page-by-page download (``pipeline``) whose scan
of that area ran to its end and whose downloads all ran (the run wasn't
stopped). Rows in the database aren't proof of that: a labels-only run or
an interrupted scan-first run writes post rows for an area it never scanned
to the end. A scan that began at ``--before`` (``scrape.start_before``)
counts as one that stopped early: it never saw the newer pages, so it leaves
the time of the last full scan as it was and, with no full scan on record,
writes no mark.

On the next run an area stops paging at the first page whose posts are all
at or below the mark, once no post with media left to download is older than
that page. A full scan happens when any of these is true (``early_stop_for``):

- no mark: the first run, or only scan-first runs (``--max-post-count``, the
  sort options) so far, which never read or write it;
- the incremental switches every other scan uses: ``--after``, incremental
  downloads off, the full-scan flag from an earlier ``--after`` run,
  ``--retry-permanent-skips``;
- ``--post-id`` or ``--force-all``;
- the database doesn't have both the mark's newest post and the oldest post
  of the last full scan. The mark is kept in the profile cache, so it
  outlives a database that was reset, restored or moved; such a mark is
  dropped at once (before the scan writes any row, or a scan stopped after
  its first page would make it look right again). Both ends are asked for
  because another kind of run (``manual``, a purchased-only run, a
  scan-first run) can write the newest post back on its own;
- the account's access to the creator changed (subscribed, following, tier),
  so older locked posts may now be viewable;
- the last full scan of the area is more than ``FANSLY_FULL_SCAN_DAYS`` days
  old. A post can appear later with an old id (scheduled, unhidden, unlocked
  on its own); no mark can see it, so a periodic full scan bounds how long it
  can be missed;
- the last full scan is dated in the future: the clock was wrong then, and
  the mark would otherwise count as fresh until the clock caught up.
"""

import logging
import time

import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.after import get_after_pre_checks
from ofscraper.data.api.common.pending import get_posts_missing_media
from ofscraper.db.operations_.messages import get_all_messages_ids
from ofscraper.db.operations_.posts import get_all_post_ids
from ofscraper.sites.fansly import scrape

log = logging.getLogger("shared")

AREAS = ("Timeline", "Messages")
# the area's own post ids, so a pending post of another area doesn't hold it
AREA_IDS = {"Timeline": get_all_post_ids, "Messages": get_all_messages_ids}
DAY = 24 * 3600


def mark_key(model_id, area):
    return f"fansly_scan_mark_v2_{model_id}_{area.lower()}"


def full_scan_days():
    return of_env.getattr("FANSLY_FULL_SCAN_DAYS")


def access(ele):
    """What decides which posts the account can see."""
    model = getattr(ele, "model", None)
    fansly = (model.get("fansly") if isinstance(model, dict) else None) or {}
    return [
        bool(fansly.get("subscribed")),
        bool(fansly.get("following")),
        str(fansly.get("tierId") or ""),
    ]


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ids(values):
    return {i for i in map(_int, values or []) if i is not None}


def newest_id(page_ids):
    ids = _ids(page_ids)
    return max(ids) if ids else None


def oldest_id(page_ids):
    ids = _ids(page_ids)
    return min(ids) if ids else None


def record(ele, area, newest, full, now=None, oldest=None):
    """Write the area's mark after its scan ran to its end in a run that
    wasn't stopped. ``newest`` and ``oldest`` are the newest and the oldest
    post id the scan saw, ``full`` whether it went to the last page rather
    than stopping early. Only a full scan's ``oldest`` is kept."""
    if area not in AREAS:
        return
    s = settings.get_settings()
    if getattr(s, "after", None) is not None or getattr(s, "post_id", None):
        # a scan cut short by --after or --post-id says nothing about older pages
        return
    if scrape.start_before() is not None:
        # a scan that began at --before didn't see the newer pages: not a full scan
        full = False
    now = time.time() if now is None else now
    old = cache.get(mark_key(ele.id, area))
    old = old if isinstance(old, dict) and old.get("access") == access(ele) else {}
    full_at = now if full else old.get("full_at")
    if full_at is None:
        return
    newest = max(
        (i for i in (_int(newest), _int(old.get("newest"))) if i is not None), default=None
    )
    oldest = _int(oldest) if full else _int(old.get("oldest"))
    if newest is None or oldest is None:
        return
    cache.set(
        mark_key(ele.id, area),
        {
            "newest": newest,
            "oldest": oldest,
            "at": now,
            "full_at": full_at,
            "access": access(ele),
        },
    )


class EarlyStop:
    """Decides, page by page, whether the rest of an area can be skipped."""

    def __init__(self, newest, pending_ids, full_at=None):
        self.newest = int(newest)
        self.pending = _ids(pending_ids)
        self.full_at = full_at

    def after_page(self, page_ids) -> bool:
        """True: stop paging this area."""
        ids = _ids(page_ids)
        if not ids or max(ids) > self.newest:
            return False
        oldest = min(ids)
        return not any(pending < oldest for pending in self.pending)


def _full_scan_reason(ele, area, mark, now):
    s = settings.get_settings()
    if get_after_pre_checks(ele.id, area) is not None:
        return "--after, incremental downloads off or a forced full scan"
    if getattr(s, "post_id", None):
        return "--post-id"
    if getattr(s, "force_all", False):
        return "--force-all"
    if not isinstance(mark, dict) or _int(mark.get("newest")) is None:
        return "no finished scan on record"
    if mark.get("access") != access(ele):
        return f"access to {ele.name} changed"
    days = full_scan_days()
    full_at = mark.get("full_at")
    if not days or days <= 0 or full_at is None or now - full_at > days * DAY:
        return f"the last full scan is more than {days} days old"
    if full_at > now:
        return "the last full scan is dated in the future"
    return None


async def early_stop_for(ele, area, now=None):
    """An ``EarlyStop`` for the area, or None for a full scan."""
    if area not in AREAS:
        return None
    now = time.time() if now is None else now
    key = mark_key(ele.id, area)
    mark = cache.get(key)
    own = set()
    if isinstance(mark, dict) and _int(mark.get("newest")) is not None:
        own = _ids(await AREA_IDS[area](model_id=ele.id, username=ele.name))
        if not {_int(mark["newest"]), _int(mark.get("oldest"))} <= own:
            # checked whatever else decides this run: the scan about to start
            # writes rows that would make a later check pass
            cache.set(key, None)
            log.debug(
                f"{area}: scanning fully: the database doesn't have the newest "
                "and the oldest post of the last scans"
            )
            return None
    reason = _full_scan_reason(ele, area, mark, now)
    if reason:
        log.debug(f"{area}: scanning fully: {reason}")
        return None
    pending = await get_posts_missing_media(ele.id, ele.name)
    return EarlyStop(mark["newest"], _ids(pending) & own, mark.get("full_at"))
