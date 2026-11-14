"""A signed CDN link rejected with 403 is fetched again once, then retried.

OnlyFans CDN links are bound to the IP that fetched them, so after an IP change
every link fetched before it answers 403. #462 stopped retrying such a link;
the downloaders now ask the API for the item again and retry once with the new
link for the same file (datawhores/OF-Scraper#653). A DRM video keeps its
manifest and gets a new signature.
"""

import asyncio
import copy
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.utils.refresh as refresh
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.utils.params import get_alt_params
import ofscraper.utils.of_env.of_env as of_env

FILE = "https://cdn2.onlyfans.com/files/a/b/clip.mp4"
OLD = f"{FILE}?Policy=old&Signature=old&Key-Pair-Id=k"
NEW = f"{FILE}?Policy=new&Signature=new&Key-Pair-Id=k"
MPD = "https://cdn3.onlyfans.com/dash/files/a/b/clip.mpd"


def _raw(post_id=100, media_id=7, link=OLD, kind="post"):
    return {
        "id": post_id,
        "responseType": kind,
        "media": [{"id": media_id, "type": "video", "files": {"full": {"url": link}}}],
    }


def _drm(signed="old", mpd=MPD):
    return {
        "manifest": {"dash": mpd},
        "signature": {
            "dash": {
                "CloudFront-Policy": f"policy-{signed}",
                "CloudFront-Signature": f"signature-{signed}",
                "CloudFront-Key-Pair-Id": "k",
            }
        },
    }


def _raw_drm(signed="old", mpd=MPD, post_id=100, media_id=7):
    return {
        "id": post_id,
        "responseType": "post",
        "media": [{"id": media_id, "type": "video", "files": {"drm": _drm(signed, mpd)}}],
    }


def _media(responsetype=None, kind="post", purchased=False, raw=None, post_id=100):
    raw = raw or _raw(post_id=post_id, kind=kind)
    post = posts_.Post(raw, 1, "a creator", responsetype, purchased=purchased)
    return post.all_media[0]


def _forbidden(url=OLD, status=403):
    info = aiohttp.RequestInfo(
        URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url)
    )
    return aiohttp.ClientResponseError(info, (), status=status)


@pytest.fixture(autouse=True)
def _fresh_story_cache(monkeypatch):
    monkeypatch.setattr(refresh, "_story_cache", {})
    monkeypatch.setattr(refresh, "_story_locks", {})


@pytest.fixture
def fetchers(monkeypatch):
    timeline = Mock(return_value=_raw(link=NEW))
    messages = AsyncMock(return_value=_raw(link=NEW, kind="message"))
    api = {}  # url -> JSON reply, for stories and highlights
    api_calls = []

    @asynccontextmanager
    async def session(**kwargs):
        yield "session"

    async def get_json(c, url):
        api_calls.append(url)
        reply = api[url]
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)

    monkeypatch.setattr(refresh, "get_individual_timeline_post", timeline)
    monkeypatch.setattr(refresh.messages_, "get_individual_messages_post", messages)
    monkeypatch.setattr(refresh, "_get_json", get_json)
    monkeypatch.setattr(
        refresh.manager, "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=session)),
    )
    return SimpleNamespace(
        timeline=timeline, messages=messages, api=api, api_calls=api_calls
    )


def _refresh(ele):
    return asyncio.run(refresh.refresh_media_link(ele))


# ---- normal files -----------------------------------------------------------


@pytest.mark.parametrize("area", [None, "timeline", "pinned", "archived", "streams"])
def test_timeline_item_gets_new_link(fetchers, area):
    ele = _media(area)
    assert _refresh(ele) is True
    fetchers.timeline.assert_called_once_with(100)
    fetchers.messages.assert_not_called()
    assert ele.url == NEW


def test_message_item_uses_message_fetcher(fetchers):
    ele = _media("messages", kind="message")
    assert _refresh(ele) is True
    fetchers.messages.assert_awaited_once_with(1, 100, "session")
    fetchers.timeline.assert_not_called()
    assert ele.url == NEW


@pytest.mark.parametrize("kind,fetcher", [("post", "timeline"), ("message", "messages")])
def test_paid_item_uses_its_purchase_type(fetchers, kind, fetcher):
    getattr(fetchers, fetcher).return_value = _raw(link=NEW, kind=kind)
    ele = _media("paid", kind=kind)
    assert _refresh(ele) is True
    assert getattr(fetchers, fetcher).call_count == 1
    assert ele.url == NEW
    # the new post keeps the item's own type
    assert ele.responsetype == "Paid"


def test_area_without_a_fetch_is_left_alone(fetchers):
    ele = _media("profile")
    assert _refresh(ele) is False
    fetchers.timeline.assert_not_called()
    fetchers.messages.assert_not_called()
    assert fetchers.api_calls == []
    assert ele.url == OLD


@pytest.mark.parametrize(
    "reply",
    [
        None,
        {"error": True},
        _raw(post_id=999, link=NEW),  # another post
        _raw(media_id=8, link=NEW),  # the post no longer has this media
        _raw(link=OLD),  # the same link again
        _raw(link="https://cdn2.onlyfans.com/files/a/b/other.mp4?Policy=new"),
        _raw(link="https://cdn3.onlyfans.com/files/a/b/clip.mp4?Policy=new"),
        RuntimeError("API down"),
    ],
    ids=["none", "error", "other-post", "no-media", "same-link",
         "other-path", "other-host", "raises"],
)
def test_unusable_reply_keeps_the_link(fetchers, reply):
    if isinstance(reply, Exception):
        fetchers.timeline.side_effect = reply
    else:
        fetchers.timeline.return_value = reply
    ele = _media()
    assert _refresh(ele) is False
    assert ele.url == OLD


# ---- stories and highlights -------------------------------------------------


def _stories_url():
    return of_env.getattr("highlightsWithAStoryEP").format(1)


def _highlights_url(offset):
    return of_env.getattr("highlightsWithStoriesEP").format(1, offset)


def _highlight_url(highlight_id):
    return of_env.getattr("storyEP").format(highlight_id)


def test_story_is_found_in_the_active_stories(fetchers):
    fetchers.api[_stories_url()] = [_raw(post_id=99, link=NEW), _raw(link=NEW)]
    ele = _media("stories")
    assert _refresh(ele) is True
    assert fetchers.api_calls == [_stories_url()]
    assert ele.url == NEW
    assert ele.responsetype == "Stories"


def test_expired_story_keeps_the_link(fetchers):
    fetchers.api[_stories_url()] = [_raw(post_id=99, link=NEW)]
    ele = _media("stories")
    assert _refresh(ele) is False
    assert ele.url == OLD


def _highlights_api(fetchers):
    fetchers.api[_highlights_url(0)] = {"list": [{"id": 1}, {"id": 2}], "hasMore": True}
    fetchers.api[_highlights_url(2)] = {"list": [{"id": 3}], "hasMore": False}
    fetchers.api[_highlight_url(1)] = {"stories": [_raw(post_id=10, link=NEW)]}
    fetchers.api[_highlight_url(2)] = {"stories": []}
    fetchers.api[_highlight_url(3)] = {
        "stories": [_raw(post_id=100, link=NEW), _raw(post_id=101, link=NEW)]
    }


def test_highlight_is_found_across_highlight_pages(fetchers):
    _highlights_api(fetchers)
    ele = _media("highlights")
    assert _refresh(ele) is True
    assert fetchers.api_calls == [
        _highlights_url(0), _highlights_url(2),
        _highlight_url(1), _highlight_url(2), _highlight_url(3),
    ]
    assert ele.url == NEW
    assert ele.responsetype == "Highlights"


def test_highlights_are_fetched_once_for_items_failing_together(fetchers):
    _highlights_api(fetchers)
    items = [_media("highlights", post_id=pid) for pid in (100, 101, 10)]

    async def all_at_once():
        return await asyncio.gather(*(refresh.refresh_media_link(e) for e in items))

    assert asyncio.run(all_at_once()) == [True, True, True]
    assert len(fetchers.api_calls) == 5
    assert all(e.url == NEW for e in items)


def test_highlight_list_is_fetched_again_after_the_cache_expires(fetchers, monkeypatch):
    _highlights_api(fetchers)
    now = [1000.0]
    monkeypatch.setattr(refresh.time, "monotonic", lambda: now[0])
    assert _refresh(_media("highlights")) is True
    now[0] += refresh.STORY_CACHE_SECONDS + 1
    assert _refresh(_media("highlights", post_id=101)) is True
    assert len(fetchers.api_calls) == 10


def test_failed_highlight_fetch_is_not_cached(fetchers):
    _highlights_api(fetchers)
    fetchers.api[_highlight_url(2)] = RuntimeError("API down")
    ele = _media("highlights")
    assert _refresh(ele) is False
    assert ele.url == OLD
    fetchers.api[_highlight_url(2)] = {"stories": []}
    assert _refresh(ele) is True
    assert ele.url == NEW


# ---- DRM videos -------------------------------------------------------------


def test_drm_video_gets_a_new_signature(fetchers):
    fetchers.timeline.return_value = _raw_drm("new")
    ele = _media(raw=_raw_drm("old"))
    assert ele.protected
    assert _refresh(ele) is True
    assert ele.mpd == MPD
    assert get_alt_params(ele) == {
        "Policy": "policy-new", "Key-Pair-Id": "k", "Signature": "signature-new"
    }


def test_drm_highlight_gets_a_new_signature(fetchers):
    fetchers.api[_stories_url()] = [_raw_drm("new")]
    ele = _media("stories", raw=_raw_drm("old"))
    assert _refresh(ele) is True
    assert get_alt_params(ele)["Signature"] == "signature-new"


@pytest.mark.parametrize(
    "reply",
    [
        _raw_drm("old"),  # the same signature
        _raw_drm("new", mpd="https://cdn3.onlyfans.com/dash/files/a/b/other.mpd"),
        _raw(link=NEW),  # no longer DRM
        {
            "id": 100, "responseType": "post",
            "media": [{"id": 7, "type": "video", "files": {"drm": {"manifest": {"dash": MPD}}}}],
        },
    ],
    ids=["same-signature", "other-manifest", "not-drm", "no-signature"],
)
def test_unusable_drm_reply_keeps_the_signature(fetchers, reply):
    fetchers.timeline.return_value = reply
    ele = _media(raw=_raw_drm("old"))
    assert _refresh(ele) is False
    assert get_alt_params(ele)["Signature"] == "signature-old"


# ---- the downloaders --------------------------------------------------------


class _MainDownloader(md.MainDownloadManager):
    """The attempts loop is replaced: each call takes the next outcome."""

    def __init__(self, outcomes):
        super().__init__()
        self.outcomes = list(outcomes)
        self.urls = []

    async def _main_download_attempts(self, c, ele):
        self.urls.append(ele.url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _AltDownloader(ad.AltDownloadManager):
    """The item download is replaced: each call takes the next outcome."""

    def __init__(self, outcomes):
        super().__init__()
        self.outcomes = list(outcomes)
        self.signatures = []

    async def _alt_download_item(self, c, ele, username, model_id):
        self.signatures.append(get_alt_params(ele)["Signature"])
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _main(downloader, ele):
    return asyncio.run(downloader._main_download_downloader(None, ele))


def _alt(downloader, ele):
    async def go():
        common_globals.sem = asyncio.Semaphore(1)
        try:
            return await downloader.alt_download(None, ele, "a creator", 1)
        finally:
            assert common_globals.sem._value == 1

    return asyncio.run(go())


@pytest.fixture
def refresher(monkeypatch):
    calls = []

    async def fake(ele):
        calls.append(ele)
        if ele.protected:
            ele.media["files"]["drm"] = _drm("new")
        else:
            ele.url = NEW
        return True

    monkeypatch.setattr(md, "refresh_media_link", fake)
    monkeypatch.setattr(ad, "refresh_media_link", fake)
    monkeypatch.setattr(common_globals, "sem", None, raising=False)
    return calls


def test_signed_403_refreshes_once_and_retries(refresher):
    ele = _media()
    downloader = _MainDownloader([_forbidden(), (10, "part", None)])
    assert _main(downloader, ele) == (10, "part", None)
    assert downloader.urls == [OLD, NEW]
    assert refresher == [ele]


def test_second_signed_403_fails_without_another_refresh(refresher):
    ele = _media()
    second = _forbidden(NEW)
    downloader = _MainDownloader([_forbidden(), second])
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        _main(downloader, ele)
    assert caught.value is second
    assert len(refresher) == 1


def test_no_new_link_raises_the_original_403(monkeypatch):
    monkeypatch.setattr(md, "refresh_media_link", AsyncMock(return_value=False))
    first = _forbidden()
    downloader = _MainDownloader([first])
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        _main(downloader, _media())
    assert caught.value is first
    assert downloader.urls == [OLD]


OTHER_ERRORS = [
    _forbidden(status=500),
    _forbidden(url=FILE),  # not signed
    _forbidden(url="https://onlyfans.com/api2/v2/posts/100"),
    OSError("disk"),
]
OTHER_IDS = ["500", "unsigned", "api-403", "oserror"]


@pytest.mark.parametrize("error", OTHER_ERRORS, ids=OTHER_IDS)
def test_other_errors_do_not_refresh(refresher, error):
    downloader = _MainDownloader([error])
    with pytest.raises(type(error)):
        _main(downloader, _media())
    assert refresher == []


DRM_403 = f"{MPD}?Policy=old&Signature=old&Key-Pair-Id=k"


def test_drm_signed_403_refreshes_once_and_retries(refresher):
    ele = _media(raw=_raw_drm("old"))
    downloader = _AltDownloader([_forbidden(DRM_403), ("Videos", 10)])
    assert _alt(downloader, ele) == ("Videos", 10)
    assert downloader.signatures == ["signature-old", "signature-new"]
    assert refresher == [ele]


def test_drm_second_signed_403_fails_without_another_refresh(refresher):
    ele = _media(raw=_raw_drm("old"))
    second = _forbidden(DRM_403)
    downloader = _AltDownloader([_forbidden(DRM_403), second])
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        _alt(downloader, ele)
    assert caught.value is second
    assert len(refresher) == 1


def test_drm_no_new_signature_raises_the_original_403(monkeypatch):
    monkeypatch.setattr(ad, "refresh_media_link", AsyncMock(return_value=False))
    first = _forbidden(DRM_403)
    downloader = _AltDownloader([first])
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        _alt(downloader, _media(raw=_raw_drm("old")))
    assert caught.value is first
    assert downloader.signatures == ["signature-old"]


@pytest.mark.parametrize("error", OTHER_ERRORS, ids=OTHER_IDS)
def test_drm_other_errors_do_not_refresh(refresher, error):
    downloader = _AltDownloader([error])
    with pytest.raises(type(error)):
        _alt(downloader, _media(raw=_raw_drm("old")))
    assert refresher == []
