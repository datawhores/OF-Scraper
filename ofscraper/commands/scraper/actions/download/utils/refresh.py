"""Fetch a newly signed CDN link for one media item.

An OnlyFans CDN link carries a CloudFront policy bound to the IP that fetched
it. After an IP change (an ISP reconnect, a VPN switch) every link fetched
before it answers 403 for the rest of the run. Fetching the post again from the
API gives links signed for the current IP.

Based on datawhores/OF-Scraper#653 by danijel1124.
"""

import asyncio
import logging
from urllib.parse import urlsplit

import ofscraper.classes.of.posts as posts_
import ofscraper.data.api.messages as messages_
import ofscraper.managers.manager as manager
from ofscraper.data.api.common.timeline import get_individual_timeline_post

log = logging.getLogger("shared")

TIMELINE_AREAS = {"Timeline", "Pinned", "Archived", "Streams"}


def _endpoint(ele):
    """"timeline", "messages", or None when the item has no single-post fetch."""
    area = ele.responsetype
    if area in TIMELINE_AREAS:
        return "timeline"
    if area == "Messages":
        return "messages"
    purchase = getattr(ele._post, "purchase_type", None)
    if purchase == "post":
        return "timeline"
    if purchase == "message":
        return "messages"
    return None


async def _fetch_post(ele, endpoint):
    if endpoint == "timeline":
        return await asyncio.to_thread(get_individual_timeline_post, ele.post_id)
    async with manager.Manager.session.aget_ofsession() as c:
        return await messages_.get_individual_messages_post(
            ele.model_id, ele.post_id, c
        )


def _same_file(old_url, new_url):
    # the .part is named before the download starts, so only a link to the
    # same file may continue it
    old, new = urlsplit(old_url), urlsplit(new_url)
    return (old.hostname, old.path) == (new.hostname, new.path)


async def refresh_media_url(ele) -> bool:
    """Set ``ele.url`` to a newly signed link for the same file.

    Returns True if the link changed. Any failure is logged and returns False,
    so the download fails as it would have without a refresh.
    """
    old_url = ele.url
    endpoint = _endpoint(ele)
    if not endpoint or not old_url:
        log.debug(f"Media {ele.id}: no way to fetch a new link for {ele.responsetype}")
        return False
    try:
        raw = await _fetch_post(ele, endpoint)
    except Exception as E:
        log.debug(f"Media {ele.id}: fetching a new link failed: {E}")
        return False
    if (
        not isinstance(raw, dict)
        or raw.get("error")
        or str(raw.get("id")) != str(ele.post_id)
    ):
        log.debug(f"Media {ele.id}: the API didn't return post {ele.post_id}")
        return False
    post = posts_.Post(
        raw,
        ele.model_id,
        ele.username,
        ele._post._responsetype,
        purchased=getattr(ele._post, "_purchased", False),
    )
    media = next((m for m in post.all_media if str(m.id) == str(ele.id)), None)
    new_url = media.url if media else None
    if not new_url or new_url == old_url:
        log.debug(f"Media {ele.id}: the API returned no new link")
        return False
    if not _same_file(old_url, new_url):
        log.debug(f"Media {ele.id}: the new link is for a different file, not using it")
        return False
    ele.url = new_url
    log.info(f"Media {ele.id}: the download link was rejected (403), using a newly signed one")
    return True
