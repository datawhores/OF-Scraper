"""Fetch a newly signed CDN link for one media item.

An OnlyFans CDN link carries a CloudFront policy bound to the IP that fetched
it. After an IP change (an ISP reconnect, a VPN switch) every link fetched
before it answers 403 for the rest of the run. Fetching the item again from the
API gives links signed for the current IP.

A normal file gets a new URL. A DRM video keeps its manifest URL but gets a new
signature (``files.drm``), which signs the manifest and segment requests.

Based on datawhores/OF-Scraper#653 by danijel1124.
"""

import asyncio
import copy
import logging
import time
from urllib.parse import urlsplit

import ofscraper.classes.of.posts as posts_
import ofscraper.data.api.messages as messages_
import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.data.api.highlights import get_highlightList

log = logging.getLogger("shared")

TIMELINE_AREAS = {"Timeline", "Pinned", "Archived", "Streams"}

# Stories and highlights have no single-item fetch, so a creator's whole list
# is fetched once and kept this long for the other items that fail after the
# same IP change
STORY_CACHE_SECONDS = 300
_story_cache = {}
_story_locks = {}


def _endpoint(ele):
    """How to fetch the item again, or None when it can't be."""
    area = ele.responsetype
    if area in TIMELINE_AREAS:
        return "timeline"
    if area == "Messages":
        return "messages"
    if area == "Stories":
        return "stories"
    if area == "Highlights":
        return "highlights"
    purchase = getattr(ele._post, "purchase_type", None)
    if purchase == "post":
        return "timeline"
    if purchase == "message":
        return "messages"
    return None


async def _get_json(c, url):
    async with c.requests_async(url=url) as r:
        if not (200 <= r.status < 300):
            raise Exception(f"{r.status} for {url}")
        return await r.json_()


async def _active_stories(c, model_id):
    data = await _get_json(c, of_env.getattr("highlightsWithAStoryEP").format(model_id))
    return data if isinstance(data, list) else []


async def _highlight_stories(c, model_id):
    highlight_ids = []
    offset = 0
    while True:
        data = await _get_json(
            c, of_env.getattr("highlightsWithStoriesEP").format(model_id, offset)
        )
        page = get_highlightList(data)
        if not page:
            break
        highlight_ids.extend(page)
        if not data.get("hasMore"):
            break
        offset += len(page)
    stories = []
    for highlight_id in highlight_ids:
        data = await _get_json(c, of_env.getattr("storyEP").format(highlight_id))
        stories.extend(data.get("stories") or [] if isinstance(data, dict) else [])
    return stories


async def _stories_by_id(model_id, area):
    key = (model_id, area)
    # an asyncio.Lock belongs to one event loop, and each run has its own
    lock = _story_locks.setdefault((id(asyncio.get_running_loop()), key), asyncio.Lock())
    async with lock:
        cached = _story_cache.get(key)
        if cached and time.monotonic() - cached[0] < STORY_CACHE_SECONDS:
            return cached[1]
        fetch = _active_stories if area == "stories" else _highlight_stories
        async with manager.Manager.session.aget_ofsession() as c:
            stories = await fetch(c, model_id)
        by_id = {str(s.get("id")): s for s in stories if isinstance(s, dict)}
        _story_cache[key] = (time.monotonic(), by_id)
        return by_id


async def _fetch_post(ele, endpoint):
    if endpoint == "timeline":
        return await asyncio.to_thread(get_individual_timeline_post, ele.post_id)
    if endpoint == "messages":
        async with manager.Manager.session.aget_ofsession() as c:
            return await messages_.get_individual_messages_post(
                ele.model_id, ele.post_id, c
            )
    return (await _stories_by_id(ele.model_id, endpoint)).get(str(ele.post_id))


def _same_file(old_url, new_url):
    # the parts are named before the download starts, so only a link to the
    # same file may continue them
    old, new = urlsplit(old_url), urlsplit(new_url)
    return (old.hostname, old.path) == (new.hostname, new.path)


def _use_new_url(ele, media):
    old_url, new_url = ele.url, media.url
    if not new_url or new_url == old_url:
        return "the API returned no new link"
    if not _same_file(old_url, new_url):
        return "the new link is for a different file, not using it"
    ele.url = new_url
    return None


def _use_new_signature(ele, media):
    old_mpd, new_mpd = ele.mpd, media.mpd if media.protected else None
    if not new_mpd:
        return "the API returned no DRM manifest"
    if not _same_file(old_mpd, new_mpd):
        return "the new manifest is for a different file, not using it"
    old_drm = ele.media.get("files", {}).get("drm") or {}
    new_drm = media.media.get("files", {}).get("drm") or {}
    new_signature = new_drm.get("signature")
    if not new_signature or new_signature == old_drm.get("signature"):
        return "the API returned no new signature"
    # the parsed manifest stays: same file, same segment names
    ele.media.setdefault("files", {})["drm"] = copy.deepcopy(new_drm)
    return None


async def refresh_media_link(ele) -> bool:
    """Give ``ele`` a newly signed link (or DRM signature) for the same file.

    Returns True if it changed. Any failure is logged and returns False, so the
    download fails as it would have without a refresh.
    """
    protected = ele.protected
    endpoint = _endpoint(ele)
    if not endpoint or not (ele.mpd if protected else ele.url):
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
        log.debug(f"Media {ele.id}: the API didn't return item {ele.post_id}")
        return False
    post = posts_.Post(
        raw,
        ele.model_id,
        ele.username,
        ele._post._responsetype,
        purchased=getattr(ele._post, "_purchased", False),
    )
    media = next((m for m in post.all_media if str(m.id) == str(ele.id)), None)
    if not media:
        log.debug(f"Media {ele.id}: the API returned the item without this media")
        return False
    problem = (_use_new_signature if protected else _use_new_url)(ele, media)
    if problem:
        log.debug(f"Media {ele.id}: {problem}")
        return False
    log.info(
        f"Media {ele.id}: the download link was rejected (403), using a newly signed one"
    )
    return True
