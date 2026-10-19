"""
Re-fetch a fresh signed CDN url for a single media item.

OnlyFans CDN urls carry a CloudFront policy that is bound to the client IP
(AWS:SourceIp). After an IP change (e.g. a nightly forced reconnect) every
url scraped before the change answers 403, no matter how often it is retried.
Re-requesting the post from the API yields urls signed for the current IP.
"""

import urllib.parse

import ofscraper.classes.of.posts as posts_
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.commands.scraper.actions.utils.log as common_logs
import ofscraper.utils.of_env.of_env as of_env

TIMELINE_TYPES = {"Timeline", "Pinned", "Archived", "Streams"}


async def _fetch_timeline_post(c, ele):
    url = of_env.getattr("INDIVIDUAL_TIMELINE").format(ele.post_id)
    async with c.requests_async(url=url) as r:
        data = await r.json_()
    return [data] if isinstance(data, dict) and not data.get("error") else []


async def _fetch_message_posts(c, ele):
    url = of_env.getattr("messageSPECIFIC").format(ele.model_id, ele.post_id)
    async with c.requests_async(url=url) as r:
        data = await r.json_()
    return data.get("list") or [] if isinstance(data, dict) else []


async def _fetch_candidates(c, ele):
    responsetype = ele.responsetype
    if responsetype in TIMELINE_TYPES:
        return await _fetch_timeline_post(c, ele)
    if responsetype == "Messages":
        return await _fetch_message_posts(c, ele)
    if responsetype == "Purchased":
        if ele.post.post.get("responseType") == "message":
            return await _fetch_message_posts(c, ele)
        return await _fetch_timeline_post(c, ele)
    return None


def _same_file(old_url, new_url):
    old, new = urllib.parse.urlsplit(old_url), urllib.parse.urlsplit(new_url)
    return (old.netloc, old.path) == (new.netloc, new.path)


async def refresh_media_url(c, ele) -> bool:
    """
    Replace ele.url with a freshly signed url for the same file.
    Returns True if the url was replaced.
    """
    log = common_globals.log
    medialog = common_logs.get_medialog(ele)
    try:
        candidates = await _fetch_candidates(c, ele)
    except Exception as E:
        log.debug(f"{medialog} url refresh request failed: {E}")
        return False
    if candidates is None:
        log.debug(f"{medialog} url refresh not supported for {ele.responsetype}")
        return False

    for raw_post in candidates:
        if str(raw_post.get("id")) != str(ele.post_id):
            continue
        post = posts_.Post(
            raw_post, ele.model_id, ele.username, responsetype=ele.responsetype
        )
        for media in post.all_media:
            if str(media.id) != str(ele.id):
                continue
            new_url = media.url
            if not new_url or new_url == ele.url:
                log.debug(f"{medialog} url refresh returned no new url")
                return False
            # the .part file name is fixed before the retry loop, only accept
            # a url pointing to the very same file so resume stays valid
            if not _same_file(ele.url, new_url):
                log.debug(f"{medialog} url refresh points to a different file, ignoring")
                return False
            ele.url = new_url
            log.info(f"{medialog} refreshed expired/foreign-IP download url")
            return True
    log.debug(f"{medialog} url refresh found no matching media")
    return False
