"""Fansly versions of the area fetchers OF-Scraper's post pipeline calls.

Each returns OnlyFans-shaped dicts (see ``normalize``), so the caller wraps
them in ``Post`` and writes them to the database exactly as it does for
OnlyFans.
"""

import contextlib
import logging
import time

import ofscraper.utils.settings as settings
from ofscraper.sites.fansly import api, normalize

log = logging.getLogger("shared")

# the post areas Fansly supports; others are skipped for Fansly profiles
AREAS = ("Timeline", "Messages", "Purchased", "Labels")


@contextlib.asynccontextmanager
async def _session(c):
    if c is not None:
        yield c
        return
    import ofscraper.managers.manager as manager

    async with manager.Manager.session.aget_ofsession() as session:
        yield session


def _after():
    """``--after`` as epoch seconds, or None for a full scan."""
    after = getattr(settings.get_settings(), "after", None)
    if not after:
        return None
    return getattr(after, "float_timestamp", None)


def start_before():
    """``--before`` as epoch seconds when the scan can start there, or None
    for a scan from the newest item: the option wasn't given (the setting
    then holds a date a few days ahead), or its date isn't in the past."""
    s = settings.get_settings()
    before = getattr(s, "before", None)
    if not before or not getattr(s, "before_original", None):
        return None
    seconds = getattr(before, "float_timestamp", None)
    if seconds is None or seconds + api.BEFORE_SLACK >= time.time():
        return None
    return seconds


def _only(items, post_id):
    """With ``--post-id``, only those posts or messages."""
    if not post_id:
        return items
    wanted = {str(x) for x in post_id}
    return [item for item in items if str(item["id"]) in wanted]


async def _collect(pages):
    async with contextlib.aclosing(pages) as pages:
        return [item async for page in pages for item in page]


async def timeline_pages(model_id, username, c=None, post_id=None):
    """The creator's timeline posts one page at a time, newest first, with
    the same ``--after`` stop and ``--post-id`` filter as the full list.
    With ``--before`` the first page asked for is the one at that date."""
    async with _session(c) as c:
        if post_id:
            yield _only(await api.posts_by_id(c, post_id), post_id)
            return
        before = start_before()
        if before is not None:
            log.debug(f"Fansly timeline: starting at --before for {username}")
        # a check against the profile's counts, for a scan from the newest post
        report = normalize.ScanReport() if before is None else None
        async with contextlib.aclosing(
            api.timeline_pages(c, model_id, after=_after(), before=before, report=report)
        ) as pages:
            async for page in pages:
                yield page
        # not reached when the caller stops early: the counts would be partial
        if report is not None:
            await _log_report(c, report, model_id, username)


async def _log_report(c, report, model_id, username):
    try:
        stats = await api.timeline_stats(c, model_id)
    except Exception as e:  # the check is only a report
        log.debug(f"Fansly media counts not read: {e}")
        stats = None
    log.info(report.summary(username, stats, after=_after()))


async def get_timeline_posts(model_id, username, c=None, post_id=None):
    posts = await _collect(timeline_pages(model_id, username, c=c, post_id=post_id))
    if not post_id:
        log.debug(f"Fansly timeline: {len(posts)} posts for {username}")
    return posts


async def message_pages(model_id, username, c=None, post_id=None):
    """The messages with the creator one page at a time, newest first. With
    ``--before`` the first page asked for is the one at that date."""
    async with _session(c) as c:
        group_id = api.group_id_for(await api.groups(c), model_id)
        if not group_id:
            log.info(f"No Fansly conversation with {username}")
            return
        before = start_before()
        if before is not None:
            log.debug(f"Fansly messages: starting at --before for {username}")
        async with contextlib.aclosing(
            api.messages_pages(c, group_id, after=_after(), before=before)
        ) as pages:
            async for page in pages:
                yield _only(page, post_id)


async def get_messages(model_id, username, c=None, post_id=None):
    found = await _collect(message_pages(model_id, username, c=c, post_id=post_id))
    log.debug(f"Fansly messages: {len(found)} for {username}")
    return found


async def label_names(c, model_id):
    """The creator's walls as labels, in one batch (``labels.scrape_labels``'s form)."""
    async with _session(c) as c:
        walls, has_main_wall = await api.walls(c, model_id)
        found = normalize.labels(walls, has_main_wall=has_main_wall)
    log.debug(f"Fansly walls as labels: {[x['id'] for x in found]}")
    yield found


async def label_pages(c, label, model_id):
    """One wall's posts, a timeline page at a time, newest first."""
    async with _session(c) as c:
        async with contextlib.aclosing(
            api.timeline_pages(c, model_id, wall_id=label["id"])
        ) as pages:
            async for page in pages:
                yield page


async def get_paid_posts(model_id, username, c=None):
    async with _session(c) as c:
        found = await api.purchases(c, model_id)
    log.debug(f"Fansly purchases: {len(found)} for {username}")
    return found


async def paid_pages(model_id, username, c=None):
    """The creator's purchases in chunks, each chunk's links fetched just
    before it is given (see ``api.purchase_pages``)."""
    async with _session(c) as c:
        async with contextlib.aclosing(api.purchase_pages(c, model_id)) as pages:
            async for page in pages:
                yield page


async def get_models(usernames=None, c=None):
    """Creators to scrape, as OnlyFans-shaped model dicts.

    With usernames: every value goes to ``account?usernames=``, and the
    all-digit ones (which may be account ids, or all-digit usernames) to
    ``account?ids=`` as well. Otherwise every followed account
    (``account/<me>/following``, then ``account?ids=``).
    """
    import ofscraper.utils.me as me_util

    usernames = [str(u) for u in (usernames or []) if u and u != "ALL"]
    ids = [u for u in usernames if u.isdigit()]
    async with _session(c) as c:
        if usernames:
            accounts = list(await api.accounts_by_username(c, usernames))
            if ids:
                accounts.extend(await api.accounts_by_id(c, ids))
            # a name and the id of the same creator return it twice
            seen = set()
            accounts = [
                a for a in accounts
                if str(a.get("id")) not in seen and not seen.add(str(a.get("id")))
            ]
        else:
            accounts = await api.accounts_by_id(c, await api.following_ids(c, me_util.get_id()))
    return [normalize.model(a) for a in accounts if a.get("id") and a.get("username")]
