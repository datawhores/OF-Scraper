"""Fetch a newly signed CDN link for one media item.

An OnlyFans CDN link carries a CloudFront policy bound to the IP that fetched
it. After an IP change (an ISP reconnect, a VPN switch) every link fetched
before it answers 403 for the rest of the run. Fetching the item again from the
API gives links signed for the current IP.

A normal file gets a new URL. A DRM video keeps its manifest URL but gets a new
signature (``files.drm``), which signs the manifest and segment requests.

Fansly links are signed the same way, with one difference: Fansly sometimes
gives out a link signed for another address, with no IP change on this side.
See ``_refresh_fansly``. And a refused Fansly link gets new links for every
waiting file signed for the same address range in one call
(``FanslyRefresher``).

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
import ofscraper.utils.const as const
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.data.api.highlights import get_highlightList
from ofscraper.sites.fansly import address
from ofscraper.sites.fansly import api as fansly_api
from ofscraper.sites.fansly import normalize as fansly_normalize
from ofscraper.sites.fansly import video as fansly_video

log = logging.getLogger("shared")

# how often Fansly is asked for a link that differs from the rejected one, and
# the seconds between asks
FANSLY_ASKS = 3
FANSLY_ASK_WAIT = 5

# Stories and highlights have no single-item fetch, so a creator's whole list
# is fetched once and kept this long for the other items that fail after the
# same IP change
STORY_CACHE_SECONDS = 300
_story_cache = {}
_story_locks = {}


def _endpoint(ele):
    """How to fetch the item again, or None when it can't be."""
    area = ele.responsetype
    if area in const.TIMELINE_POST_AREA_SET:
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
    if not new_url:
        return "the API returned no new link"
    if not _same_file(old_url, new_url):
        return "the new link is for a different file, not using it"
    ele.url = new_url
    return None


def _signature(ele):
    """What signs a protected video's manifest and segments."""
    return (ele.media.get("files", {}).get("drm") or {}).get("signature")


def _use_new_signature(ele, media):
    old_mpd, new_mpd = ele.mpd, media.mpd if media.protected else None
    if not new_mpd:
        return "the API returned no DRM manifest"
    if not _same_file(old_mpd, new_mpd):
        return "the new manifest is for a different file, not using it"
    new_drm = media.media.get("files", {}).get("drm") or {}
    new_signature = new_drm.get("signature")
    if not new_signature:
        return "the API returned no signature"
    # the parsed manifest stays: same file, same segment names
    ele.media.setdefault("files", {})["drm"] = copy.deepcopy(new_drm)
    return None


def _fansly_signatures(raw):
    """The signatures on every location of a raw Fansly Media."""
    out = set()
    for obj in [raw] + list(raw.get("variants") or []):
        for location in obj.get("locations") or []:
            signature = fansly_video.cloudfront_cookies(location).get("CloudFront-Signature")
            if signature:
                out.add(signature)
    return out


SAME_LINK = "Fansly gave the same link again"
THIS_FILE_ONLY = "the CDN accepts another link signed for the same address"
RANGE_UNKNOWN = "nothing shows whether the CDN refuses the address its link is signed for"
GIVEN_UP = "Fansly keeps signing links for an address the CDN refuses"
FETCH_AHEAD_OFF = "fetching links ahead is paused after failed calls"
# failed shared calls in a row before fetching links ahead pauses, and for
# how many seconds. A pause, not the rest of the run: a burst of rate
# limiting is over in a minute, and an address change may come much later
CALL_FAILURES = 3
FETCH_AHEAD_PAUSE = 120
# pauses in a row that files signed for a refused range wait out. Their links
# are refused whatever they do, and asking for each alone only feeds a rate
# limit; after these, an API that is still failing gets the per-file asks
PAUSE_WAITS = 2
# seconds the asks whose new links were refused stay counted: longer than the
# pauses a file waits out, and not for ever, because what the API signs for
# can change without a sign
REFUSED_ASKS_KEPT = 300
# the refresher's clock, apart from the event loop's so a test can move it
_clock = time.monotonic


def _raw(ele):
    return (ele.media.get("fansly") or {}).get("media")


def _fansly_ids(ele):
    """The accountMedia id to ask for, or None when the item has none."""
    details = ele.media.get("fansly") or {}
    if not details.get("media"):
        return None
    return details.get("accountMediaId")


def _apply_fansly(ele, item):
    """Give ``ele`` the links of ``item``, an ``account/media`` answer.

    Returns None when it did, otherwise why not (``SAME_LINK`` when the
    answer carries no new signature). No network.
    """
    details = ele.media.get("fansly") or {}
    old = details.get("media") or {}
    part = "preview" if details.get("isPreview") else "media"
    new = (item or {}).get(part) or {}
    if str(new.get("id")) != str(old.get("id")):
        return "the API didn't return this media"
    if not _fansly_signatures(new) - _fansly_signatures(old):
        return SAME_LINK
    new_url = fansly_normalize.file_url(new)
    if ele.url and (not new_url or not _same_file(ele.url, new_url)):
        return "the new link is for a different file, not using it"
    # the stream downloader reads its links from the raw Media
    details["media"] = new
    if new_url:
        ele.media.setdefault("files", {}).setdefault("full", {})["url"] = new_url
        ele.url = new_url
    return None


def apply_fansly_item(ele, item) -> bool:
    """True when ``ele`` now has the links of ``item`` (see ``_apply_fansly``)."""
    return _apply_fansly(ele, item) is None


def _answer_for(found, account_media_id):
    return next(
        (
            x
            for x in found or []
            if isinstance(x, dict) and str(x.get("id")) == str(account_media_id)
        ),
        {},
    )


async def _refresh_fansly(ele, asked=0) -> bool:
    """Fansly: fetch the item's accountMedia again and use its links.

    Fansly keeps a signed link for a while and gives the same one to every
    request for that media, sometimes one signed for another address, which
    its CDN refuses (#683). So this asks a few times, until a link changes.
    ``asked``: asks already made elsewhere that gave the same link.
    """
    account_media_id = _fansly_ids(ele)
    if not account_media_id:
        log.debug(f"Media {ele.id}: no way to fetch a new Fansly link")
        return False
    for ask in range(asked, FANSLY_ASKS):
        if ask:
            await asyncio.sleep(FANSLY_ASK_WAIT)
        try:
            async with manager.Manager.session.aget_ofsession() as c:
                # a link signed for a refused range: one call per ask. The
                # shared call tried the API's next address already, and
                # asking again from each address would cost five calls here
                once = {"asks": 1} if address.is_refused(ele.url) else {}
                found = await fansly_api.account_media(c, [account_media_id], **once)
        except Exception as E:
            log.debug(f"Media {ele.id}: fetching a new link failed: {E}")
            return False
        try:
            problem = _apply_fansly(ele, _answer_for(found, account_media_id))
        except Exception:
            problem = "the API's answer for this media could not be read"
        if problem == SAME_LINK:
            continue
        if problem:
            log.debug(f"Media {ele.id}: {problem}")
            return False
        log.info(
            f"Media {ele.id}: the download link was rejected (403), using a newly signed one"
        )
        return True
    log.info(
        f"Media {ele.id}: Fansly's CDN rejected the download link (403) and Fansly "
        f"gave the same link again {FANSLY_ASKS} times. It may be signed for "
        "another address; the next run tries again"
    )
    return False


def _is_fansly(ele):
    return isinstance(getattr(ele, "media", None), dict) and bool(ele.media.get("fansly"))


def _read_error(task):
    """Read a finished task's error, so the loop has none left to report."""
    if not task.cancelled():
        task.exception()


def _path(url):
    return urlsplit(url).path


class FanslyRefresher:
    """New links for every waiting Fansly item a refusal makes stale.

    When the address downloads leave from changes (a VPN switch, a
    reconnect), the CDN refuses every link signed before it, those of files
    not started yet included. Asking for each file's link on its own costs an
    ``account/media`` call per file, and Fansly allows about ten calls a
    minute; a call costs the same with ``ACCOUNT_MEDIA_BATCH`` ids. So the
    first refusal fetches new links for the waiting items whose links are
    signed for the refused range, one call for many, and the rest find their
    links already replaced.

    One 403 is not proof that a range is dead: a deleted file answers 403
    too, and the files of deleted posts wait side by side. So before a range
    is marked refused (``address.refused``), the links signed for it that
    the CDN accepted earlier in the run are tried again (one byte each, up
    to two, ``address.accepted_links``): those files were there, so a
    refusal of all of them now is about the range. If the CDN still accepts
    one, or no such link is kept,
    only this file gets a new link, on its own; when that link is signed for
    another range the CDN accepts, the address did change, and the old range
    is marked then (``_moved``).

    The shared call asks once and judges the answer itself (``_judge``). A
    link Fansly gave again unchanged (it keeps a link for a while) says
    nothing about the address the API sees now: those items are left to the
    per-file asks and move nothing. A new link does: one per range is tried
    on the CDN, which also clears a mark that was wrong or is out of date (a
    VPN that went back). When new links are signed for a range the CDN
    refuses, the API is seeing another address than the downloads leave from
    (#683): its next address is tried and the call made again, until the
    new links are accepted or every address was asked. So a shared call is
    at most ``ADDRESS_ASKS`` API calls, as for a page of the scan.

    After ``ADDRESS_ASKS`` asks in a row whose new links were refused, each
    from the API's next address, it leaves the files of the ranges those
    links were signed for to the per-file asks. The asks are counted over
    the shared calls and whatever the range, so neither an ask that fails on
    the way nor addresses that sign for two refused ranges in turn start
    them again. An ask that brings no new link changes nothing. The count
    starts again when new links are accepted, when the address downloads
    leave from changes, and ``REFUSED_ASKS_KEPT`` seconds after its last
    ask. After
    ``CALL_FAILURES`` failed shared calls in a row it pauses for
    ``FETCH_AHEAD_PAUSE`` seconds (then one more failed call pauses it
    again). Files signed for a refused range wait the first ``PAUSE_WAITS``
    pauses out and share the next call; after those they ask on their own.

    Items are added with ``expect`` and removed with ``done``; one call runs
    at a time.
    """

    def __init__(self):
        self._waiting = {}
        # id(item) -> its raw media when a shared call gave the same link
        self._stale = {}
        # ranges whose new links were refused from every API address
        self._given_up = set()
        # asks in a row whose new links the CDN refused, the ranges those
        # were signed for, and when the last one was
        self._refused_asks = 0
        self._refused_ranges = set()
        self._refused_at = 0
        # failed shared calls in a row, and until when no shared call is made
        self._failures = 0
        self._paused_until = 0
        # pauses in a row, with no shared call that worked in between
        self._pauses = 0
        self._lock = None
        self._loop = None

    def reset(self):
        self._waiting.clear()
        self._stale.clear()
        self._given_up.clear()
        self.forget_asks()
        self._failures = 0
        self._paused_until = 0
        self._pauses = 0

    def expect(self, items):
        """Items about to be downloaded, in download order."""
        for ele in items:
            if _is_fansly(ele):
                self._waiting[id(ele)] = ele

    def done(self, ele):
        self._waiting.pop(id(ele), None)
        self._stale.pop(id(ele), None)

    async def _range_refused(self, ele, link):
        """(whether the range ``link`` is signed for is refused, the other
        links that were tried): the links signed for it that the CDN
        accepted earlier are tried again. True when all of them are refused
        (one of their files may be deleted too; with two kept, both would
        have to be), False when one is accepted, None when it isn't known:
        none is kept, or a try failed."""
        tried = []
        try:
            async with manager.Manager.session.aget_ofsession() as c:
                for other in address.accepted_links(link):
                    verdict = await address.cdn_refuses(c, other)
                    if verdict is None:
                        return None, tried
                    if not verdict:
                        # the range is fine, so the refused ones are gone
                        for dead in tried:
                            address.gone(dead)
                        return False, tried
                    tried.append(other)
        except Exception as E:
            log.debug(f"Media {ele.id}: could not try another link: {type(E).__name__}")
            return None, tried
        return (True if tried else None), tried

    async def _call(self, ids):
        """``account/media`` for ``ids``, asked once. A failed call is tried
        once more, after a wait."""
        error = None
        for attempt in range(2):
            if attempt:
                await asyncio.sleep(FANSLY_ASK_WAIT)
            try:
                async with manager.Manager.session.aget_ofsession() as c:
                    found = await fansly_api.account_media(c, ids, asks=1)
                return found if isinstance(found, list) else []
            except Exception as E:
                error = E
        raise error

    def _apply(self, batch, found, ele):
        """Give the batch's items their answers. Returns why ``ele`` got no
        new link (None when it did) and the items that got one."""
        problem = "the API didn't return this media"
        changed = []
        for account_media_id, items in batch.items():
            answer = _answer_for(found, account_media_id)
            for item in items:
                try:
                    why = _apply_fansly(item, answer)
                except Exception:
                    why = "the API's answer for this media could not be read"
                if why is None:
                    changed.append(item)
                    self._stale.pop(id(item), None)
                elif why == SAME_LINK and item is not ele:
                    self._stale[id(item)] = _raw(item)
                if item is ele:
                    problem = why
        return problem, changed

    async def _judge(self, changed, avoid):
        """The ranges of new links that the CDN refuses.

        One new link per range that isn't known to be accepted is tried on
        the CDN (not one of the files in ``avoid``, which were just refused
        and may be deleted), and what it says is kept."""
        by_range = {}
        for item in changed:
            signed_for = address.link_range(item.url)
            if signed_for:
                by_range.setdefault(signed_for, []).append(item.url)
        refused, accepted = set(), set()
        for signed_for, links in by_range.items():
            if not address.is_accepted(links[0]):
                link = next((u for u in links if _path(u) not in avoid), links[0])
                try:
                    async with manager.Manager.session.aget_ofsession() as c:
                        await address.try_link(c, link)
                except Exception as E:
                    log.debug(f"Fansly: could not try a new link: {type(E).__name__}")
            if address.is_refused(links[0]):
                refused.add(signed_for)
            elif address.is_accepted(links[0]):
                accepted.add(signed_for)
        return refused, accepted

    def forget_asks(self):
        """Start counting the asks whose new links are refused again."""
        self._refused_asks = 0
        self._refused_ranges = set()
        self._refused_at = 0

    def _settle(self, refused, accepted):
        """After an ask whose new links the CDN refused for the ranges in
        ``refused`` and accepted for those in ``accepted``. True when a
        refused range is given up: ``ADDRESS_ASKS`` asks in a row brought
        refused links, each from the API's next address, in this shared call
        or over several, whatever ranges they were signed for.

        A range stays given up while that row of refused asks goes on: an
        ask that doesn't bring it leaves it given up. It is tried again
        when new links are accepted, or when it isn't among the refused of
        an ask after the count started again (``forget_asks``, or
        ``REFUSED_ASKS_KEPT`` seconds without a refused ask)."""
        if not refused:
            if accepted:
                self.forget_asks()
                self._given_up.clear()
            return False
        now = _clock()
        if now - self._refused_at > REFUSED_ASKS_KEPT:
            self.forget_asks()
        self._refused_asks += 1
        self._refused_ranges |= refused
        self._refused_at = now
        self._given_up &= refused
        if (
            self._refused_asks >= fansly_api.ADDRESS_ASKS
            and self._refused_ranges - self._given_up
        ):
            self._given_up |= self._refused_ranges
            log.info(
                "Fansly keeps signing links for an address its CDN refuses. "
                "Asking for each file's link on its own from here"
            )
        return bool(refused & self._given_up)

    def _get_lock(self):
        # an asyncio.Lock belongs to one event loop, and each run has its own
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._lock = loop, asyncio.Lock()
        return self._lock

    async def fresh(self, ele, link=None):
        """Give ``ele`` new links, with the waiting items that need them too.

        ``link``: the link the CDN just refused; None before a download whose
        link is signed for a refused range. Returns None when ``ele`` has new
        links (from this call or one made while it waited), otherwise why
        not. ``SAME_LINK`` (Fansly gave its link again), ``THIS_FILE_ONLY``
        (only this link is refused), ``RANGE_UNKNOWN`` (no link to check its
        range against), ``GIVEN_UP`` and ``FETCH_AHEAD_OFF`` leave ``ele`` to
        the per-file asks.
        """
        before = _raw(ele)
        problem = await self._shielded(ele, link, before)
        if problem == FETCH_AHEAD_OFF and self._pauses <= PAUSE_WAITS:
            # this file's link is refused until a shared call works
            await asyncio.sleep(max(0.0, self._paused_until - _clock()) + 0.1)
            problem = await self._shielded(ele, link, before)
        return problem

    async def _shielded(self, ele, link, before):
        # shielded: a cancelled download must not cancel a call that other
        # downloads wait for. Its error, if any, is read either way.
        task = asyncio.ensure_future(self._fresh(ele, link, before))
        task.add_done_callback(_read_error)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            raise
        except Exception as E:
            return f"fetching a new link failed: {E}"

    async def _fresh(self, ele, link, before):
        async with self._get_lock():
            if _raw(ele) is not before:
                return None
            if link is None and not address.is_refused(ele.url):
                return None
            if (
                link is not None
                and ele.url
                and ele.url != link
                and not address.is_refused(ele.url)
            ):
                # replaced after the refused request was made
                return None
            others = []
            if link is not None and not address.is_refused(link):
                confirmed, others = await self._range_refused(ele, link)
                if not confirmed:
                    return RANGE_UNKNOWN if confirmed is None else THIS_FILE_ONLY
                address.refused(link)
                # the address downloads leave from changed
                self._given_up.discard(address.link_range(link))
                self.forget_asks()
            if before is not None and self._stale.get(id(ele)) is before:
                return SAME_LINK
            first = _fansly_ids(ele)
            if not first:
                return "no way to fetch a new Fansly link"
            signed_for = address.link_range(link or ele.url)
            if signed_for in self._given_up:
                return GIVEN_UP
            if _clock() < self._paused_until:
                return FETCH_AHEAD_OFF
            batch = {str(first): [ele]}
            for item in self._waiting.values():
                if len(batch) >= fansly_api.ACCOUNT_MEDIA_BATCH:
                    break
                item_id = _fansly_ids(item)
                if item is ele or not item_id or not address.is_refused(item.url):
                    continue
                batch.setdefault(str(item_id), []).append(item)
            avoid = {_path(u) for u in (link, *others) if u}
            got_new, problem, replaced = False, None, set()
            for _ in range(fansly_api.ADDRESS_ASKS):
                try:
                    found = await self._call(list(batch))
                except Exception as E:
                    self._failures += 1
                    if self._failures >= CALL_FAILURES:
                        self._paused_until = _clock() + FETCH_AHEAD_PAUSE
                        self._pauses += 1
                        log.info(
                            "Fetching Fansly links ahead keeps failing. "
                            + (
                                f"Waiting {FETCH_AHEAD_PAUSE} seconds before the next try"
                                if self._pauses <= PAUSE_WAITS
                                else "Asking for each file's link on its own "
                                f"for the next {FETCH_AHEAD_PAUSE} seconds"
                            )
                        )
                    if got_new:
                        break
                    return f"fetching a new link failed: {E}"
                self._failures = 0
                self._pauses = 0
                problem, changed = self._apply(batch, found, ele)
                got_new = got_new or problem is None
                replaced.update(id(item) for item in changed if item is not ele)
                refused, accepted = await self._judge(changed, avoid)
                if self._settle(refused, accepted) or not refused:
                    break
                # new links signed for an address the CDN refuses: the API
                # sees another address than the downloads leave from (#683)
                log.debug("Fansly: new links are signed for a refused address, asking again")
                async with manager.Manager.session.aget_ofsession() as c:
                    fansly_api.next_address(c)
            if len(batch) > 1:
                log.debug(
                    f"Fansly: fetched new links for {len(batch) - 1} waiting "
                    f"{'file' if len(batch) == 2 else 'files'} with media "
                    f"{ele.id}, {len(replaced)} replaced"
                )
            return None if got_new else problem


fansly_refresher = FanslyRefresher()


def refused_url(exception):
    """The URL of the request an HTTP error answered, or None."""
    info = getattr(exception, "request_info", None)
    url = getattr(info, "real_url", None)
    if url is None:
        try:
            url = exception.request.url
        except Exception:
            url = None
    return str(url) if url else None


async def fresh_before_download(ele):
    """Before a Fansly download: when its link is signed for a range the CDN
    refuses, fetch new links first (usually already done by an earlier
    call), so the download doesn't spend a request on a 403."""
    if not _is_fansly(ele) or not address.is_refused(ele.url):
        return
    problem = await fansly_refresher.fresh(ele)
    if problem:
        log.debug(f"Media {ele.id}: its link is signed for a refused address; {problem}")


def _moved(link, new):
    """A file's refused ``link`` and its ``new`` one are signed for different
    ranges, and the CDN accepts the new one's: the address downloads leave
    from changed, so the old range is marked refused and the waiting files
    signed for it share the next call."""
    if (
        address.link_range(new)
        and address.link_range(new) != address.link_range(link)
        and address.is_accepted(new)
        and not address.is_refused(link)
    ):
        address.refused(link)
        fansly_refresher.forget_asks()


async def _refresh_fansly_refused(ele, link) -> bool:
    if not address.link_range(link):
        # no address range in the link: ask for this item alone
        return await _refresh_fansly(ele)
    problem = await fansly_refresher.fresh(ele, link)
    if problem == SAME_LINK:
        # the shared call was this item's first ask
        return await _refresh_fansly(ele, asked=1)
    if problem in (THIS_FILE_ONLY, RANGE_UNKNOWN, GIVEN_UP, FETCH_AHEAD_OFF):
        log.debug(f"Media {ele.id}: {problem}; asking for its link alone")
        changed = await _refresh_fansly(ele)
        if changed and problem == RANGE_UNKNOWN:
            # with a link of the old range just accepted, that range is
            # fine and the file was refused for a reason of its own
            _moved(link, ele.url)
        return changed
    if problem:
        log.debug(f"Media {ele.id}: {problem}")
        return False
    log.info(
        f"Media {ele.id}: the download link was rejected (403), using a newly signed one"
    )
    return True


async def refresh_media_link(ele, link=None, refusal=None) -> bool:
    """Give ``ele`` a newly signed link (or DRM signature) for the same file.

    ``link``: the link the CDN refused, when known. On Fansly a refused link
    signed for an address range also gets new links for the waiting items
    signed for that range (``FanslyRefresher``).

    ``refusal``: the error the CDN's 403 raised, when known. When the site
    still gives the refused link, the address that refused it is left
    (#620).

    Returns True if there is a link to try: a new one, or the same one when
    the site still gives it. Any failure is logged and returns False, so the
    download fails as it would have without a refresh.
    """
    if ele.media.get("fansly"):
        if link:
            return await _refresh_fansly_refused(ele, link)
        return await _refresh_fansly(ele)
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
    # The site can give the refused link again: it hasn't expired and is
    # signed for this address. So one address of the file host refused a
    # good link. Its other addresses take it: the one that refused is left
    # (sessionmanager/refusing.py), and the same link counts as a link to
    # try (#620). A protected video is signed by its signature instead: the
    # same holds when the site still gives that one (#623).
    before = _signature(ele) if protected else ele.url
    problem = (_use_new_signature if protected else _use_new_url)(ele, media)
    if problem:
        log.debug(f"Media {ele.id}: {problem}")
        return False
    still_current = before == (_signature(ele) if protected else ele.url)
    if still_current:
        leave_address = getattr(refusal, "leave_address", None)
        if leave_address:
            leave_address()
        log.info(
            f"Media {ele.id}: the download link was rejected (403) but is still"
            " the current one, trying it again"
        )
    else:
        log.info(
            f"Media {ele.id}: the download link was rejected (403), using a"
            " newly signed one"
        )
    return True
