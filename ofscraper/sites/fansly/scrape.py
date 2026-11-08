"""Fansly versions of the area fetchers OF-Scraper's post pipeline calls.

Each returns OnlyFans-shaped dicts (see ``normalize``), so the caller wraps
them in ``Post`` and writes them to the database exactly as it does for
OnlyFans.
"""

import contextlib
import logging

import ofscraper.utils.settings as settings
from ofscraper.sites.fansly import api, normalize

log = logging.getLogger("shared")

# the post areas Fansly supports; others are skipped for Fansly profiles
AREAS = ("Timeline", "Messages", "Purchased")


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


async def get_timeline_posts(model_id, username, c=None, post_id=None):
    async with _session(c) as c:
        if post_id:
            posts = await api.posts_by_id(c, post_id)
            return [p for p in posts if str(p["id"]) in {str(x) for x in post_id}]
        posts = await api.timeline(c, model_id, after=_after())
    log.debug(f"Fansly timeline: {len(posts)} posts for {username}")
    return posts


async def get_messages(model_id, username, c=None, post_id=None):
    async with _session(c) as c:
        group_id = api.group_id_for(await api.groups(c), model_id)
        if not group_id:
            log.info(f"No Fansly conversation with {username}")
            return []
        found = await api.messages(c, group_id, after=_after())
    if post_id:
        found = [m for m in found if str(m["id"]) in {str(x) for x in post_id}]
    log.debug(f"Fansly messages: {len(found)} for {username}")
    return found


async def get_paid_posts(model_id, username, c=None):
    async with _session(c) as c:
        found = await api.purchases(c, model_id)
    log.debug(f"Fansly purchases: {len(found)} for {username}")
    return found


async def get_models(usernames=None):
    """Creators to scrape, as OnlyFans-shaped model dicts.

    With usernames: every value goes to ``account?usernames=``, and the
    all-digit ones (which may be account ids, or all-digit usernames) to
    ``account?ids=`` as well. Otherwise every followed account
    (``account/<me>/following``, then ``account?ids=``).
    """
    import ofscraper.utils.me as me_util

    usernames = [str(u) for u in (usernames or []) if u and u != "ALL"]
    ids = [u for u in usernames if u.isdigit()]
    async with _session(None) as c:
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
