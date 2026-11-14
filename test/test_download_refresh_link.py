"""A signed CDN link rejected with 403 is fetched again once, then retried.

OnlyFans CDN links are bound to the IP that fetched them, so after an IP change
every link fetched before it answers 403. #462 stopped retrying such a link;
the normal downloader now asks the API for the post again and retries once
with the new link for the same file (datawhores/OF-Scraper#653).
"""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.utils.refresh as refresh

FILE = "https://cdn2.onlyfans.com/files/a/b/clip.mp4"
OLD = f"{FILE}?Policy=old&Signature=old&Key-Pair-Id=k"
NEW = f"{FILE}?Policy=new&Signature=new&Key-Pair-Id=k"


def _raw(post_id=100, media_id=7, link=OLD, kind="post"):
    return {
        "id": post_id,
        "responseType": kind,
        "media": [{"id": media_id, "type": "video", "files": {"full": {"url": link}}}],
    }


def _media(responsetype=None, kind="post", purchased=False):
    post = posts_.Post(_raw(kind=kind), 1, "a creator", responsetype, purchased=purchased)
    return post.all_media[0]


def _forbidden(url=OLD, status=403):
    info = aiohttp.RequestInfo(
        URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url)
    )
    return aiohttp.ClientResponseError(info, (), status=status)


@pytest.fixture
def fetchers(monkeypatch):
    timeline = Mock(return_value=_raw(link=NEW))
    messages = AsyncMock(return_value=_raw(link=NEW, kind="message"))

    @asynccontextmanager
    async def session(**kwargs):
        yield "session"

    monkeypatch.setattr(refresh, "get_individual_timeline_post", timeline)
    monkeypatch.setattr(refresh.messages_, "get_individual_messages_post", messages)
    monkeypatch.setattr(
        refresh.manager, "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=session)),
    )
    return SimpleNamespace(timeline=timeline, messages=messages)


@pytest.mark.parametrize("area", [None, "timeline", "pinned", "archived", "streams"])
def test_timeline_item_gets_new_link(fetchers, area):
    ele = _media(area)
    assert asyncio.run(refresh.refresh_media_url(ele)) is True
    fetchers.timeline.assert_called_once_with(100)
    fetchers.messages.assert_not_called()
    assert ele.url == NEW


def test_message_item_uses_message_fetcher(fetchers):
    ele = _media("messages", kind="message")
    assert asyncio.run(refresh.refresh_media_url(ele)) is True
    fetchers.messages.assert_awaited_once_with(1, 100, "session")
    fetchers.timeline.assert_not_called()
    assert ele.url == NEW


@pytest.mark.parametrize("kind,fetcher", [("post", "timeline"), ("message", "messages")])
def test_paid_item_uses_its_purchase_type(fetchers, kind, fetcher):
    getattr(fetchers, fetcher).return_value = _raw(link=NEW, kind=kind)
    ele = _media("paid", kind=kind)
    assert asyncio.run(refresh.refresh_media_url(ele)) is True
    assert getattr(fetchers, fetcher).call_count == 1
    assert ele.url == NEW
    # the new post keeps the item's own type
    assert ele.responsetype == "Paid"


@pytest.mark.parametrize("area", ["stories", "highlights", "profile"])
def test_area_without_single_post_fetch_is_left_alone(fetchers, area):
    ele = _media(area)
    assert asyncio.run(refresh.refresh_media_url(ele)) is False
    fetchers.timeline.assert_not_called()
    fetchers.messages.assert_not_called()
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
    assert asyncio.run(refresh.refresh_media_url(ele)) is False
    assert ele.url == OLD


class _Downloader(md.MainDownloadManager):
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


def _download(downloader, ele):
    return asyncio.run(downloader._main_download_downloader(None, ele))


@pytest.fixture
def refresher(monkeypatch):
    calls = []

    async def fake(ele):
        calls.append(ele)
        ele.url = NEW
        return True

    monkeypatch.setattr(md, "refresh_media_url", fake)
    return calls


def test_signed_403_refreshes_once_and_retries(refresher):
    ele = _media()
    downloader = _Downloader([_forbidden(), (10, "part", None)])
    assert _download(downloader, ele) == (10, "part", None)
    assert downloader.urls == [OLD, NEW]
    assert refresher == [ele]


def test_second_signed_403_fails_without_another_refresh(refresher):
    ele = _media()
    second = _forbidden(NEW)
    downloader = _Downloader([_forbidden(), second])
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        _download(downloader, ele)
    assert caught.value is second
    assert len(refresher) == 1


def test_no_new_link_raises_the_original_403(monkeypatch):
    monkeypatch.setattr(md, "refresh_media_url", AsyncMock(return_value=False))
    first = _forbidden()
    downloader = _Downloader([first])
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        _download(downloader, _media())
    assert caught.value is first
    assert downloader.urls == [OLD]


@pytest.mark.parametrize(
    "error",
    [
        _forbidden(status=500),
        _forbidden(url=FILE),  # not signed
        _forbidden(url="https://onlyfans.com/api2/v2/posts/100"),
        OSError("disk"),
    ],
    ids=["500", "unsigned", "api-403", "oserror"],
)
def test_other_errors_do_not_refresh(refresher, error):
    downloader = _Downloader([error])
    with pytest.raises(type(error)):
        _download(downloader, _media())
    assert refresher == []
