"""Fansly: a signed link the CDN rejects (403) is fetched again (#683).

Fansly sometimes gives out a link signed for another address. Its CDN refuses
that link until Fansly signs a new one, and Fansly may return the same link
for a while, so the refresh asks a few times.
"""

import asyncio
import copy
import json
import pathlib
from contextlib import asynccontextmanager
from types import SimpleNamespace

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.utils.refresh as refresh
import ofscraper.managers.sessionmanager.sessionmanager as sm
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.sites.fansly import video

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "fansly"


def signed(tag):
    """The fixture's accountMedia with every location signed as ``tag``."""
    data = json.loads((FIXTURES / "video_4k_account_media.json").read_text(encoding="utf-8"))
    item = copy.deepcopy(data["response"][0])
    keys = {"Policy": f"policy-{tag}", "Signature": f"signature-{tag}", "Key-Pair-Id": "k"}
    media = item["media"]
    for obj in [media] + media["variants"]:
        for location in obj["locations"]:
            if location.get("metadata"):
                location["metadata"] = dict(keys)
            else:
                base = location["location"].split("?")[0]
                location["location"] = base + "?" + "&".join(f"{k}={v}" for k, v in keys.items())
    return item


def direct(item):
    return item["media"]["locations"][0]["location"]


def make_ele(item):
    raw = item["media"]
    media = {
        "id": int(raw["id"]),
        "type": "video",
        "canView": True,
        "files": {"full": {"url": direct(item)}},
        "fansly": {
            "accountMediaId": item["id"],
            "mediaId": raw["id"],
            "isPreview": False,
            "media": raw,
        },
    }
    post = Post(
        {"id": 100000000000000005, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        100000000000000002,
        "a-creator",
        responsetype="timeline",
    )
    return Media(media, 0, post)


@pytest.fixture
def fansly(monkeypatch):
    """Replies of ``account/media``, one per ask; the last one repeats."""
    replies, asked, waits = [], [], []

    @asynccontextmanager
    async def session(**kwargs):
        yield "session"

    async def account_media(c, ids):
        asked.append(list(ids))
        reply = replies[min(len(asked), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(refresh.fansly_api, "account_media", account_media)
    monkeypatch.setattr(refresh.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        refresh.manager, "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=session)),
    )
    return SimpleNamespace(replies=replies, asked=asked, waits=waits)


def run(ele):
    return asyncio.run(refresh.refresh_media_link(ele))


def test_a_new_link_replaces_the_url_and_the_stream_links(fansly):
    old, new = signed("old"), signed("new")
    ele = make_ele(old)
    fansly.replies.append([new])
    assert run(ele) is True
    assert fansly.asked == [[old["id"]]]
    assert ele.url == direct(new)
    assert ele.media["files"]["full"]["url"] == direct(new)
    best = video.select_best(video.raw_media(ele))
    assert best.is_stream and best.cookies["CloudFront-Signature"] == "signature-new"


def test_the_same_link_is_asked_for_again_until_it_changes(fansly):
    old = signed("old")
    ele = make_ele(old)
    fansly.replies.extend([[old], [signed("new")]])
    assert run(ele) is True
    assert len(fansly.asked) == 2 and fansly.waits == [refresh.FANSLY_ASK_WAIT]
    assert ele.url == direct(signed("new"))


def test_a_link_that_never_changes_gives_up_and_says_why(fansly, caplog):
    old = signed("old")
    ele = make_ele(old)
    fansly.replies.append([old])
    with caplog.at_level("INFO", logger="shared"):
        assert run(ele) is False
    assert len(fansly.asked) == refresh.FANSLY_ASKS
    assert ele.url == direct(old)
    assert "signed for another address" in caplog.text


@pytest.mark.parametrize("case", ["missing", "other_media", "other_file", "api_error"])
def test_an_unusable_reply_changes_nothing(fansly, case):
    old, new = signed("old"), signed("new")
    ele = make_ele(old)
    if case == "missing":
        fansly.replies.append([])
    elif case == "other_media":
        new["media"]["id"] = "100000000000000099"
        fansly.replies.append([new])
    elif case == "other_file":
        location = new["media"]["locations"][0]
        location["location"] = location["location"].replace("100000000000000019.mp4", "other.mp4")
        fansly.replies.append([new])
    else:
        fansly.replies.append(RuntimeError("503"))
    assert run(ele) is False
    assert len(fansly.asked) == 1
    assert ele.url == direct(old)
    assert video.raw_media(ele) is old["media"]


def test_a_locked_item_refreshes_its_preview(fansly):
    old, new = signed("old"), signed("new")
    for item in (old, new):
        item["preview"] = item.pop("media")
        item["media"] = {"id": "100000000000000098", "locations": []}
    ele = make_ele({**old, "media": old["preview"]})
    ele.media["fansly"]["isPreview"] = True
    fansly.replies.append([new])
    assert run(ele) is True
    assert ele.url == new["preview"]["locations"][0]["location"]


def forbidden(url, status=403):
    info = aiohttp.RequestInfo(URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url))
    return aiohttp.ClientResponseError(info, (), status=status)


def test_a_rejected_signed_fansly_link_is_not_retried_as_it_is():
    link = direct(signed("old"))
    assert sm.is_signed_cdn_forbidden(forbidden(link)) is True
    # an unsigned stream file (its cookies sign it) is still retried: a
    # refused segment often works on the next try
    segment = "https://cdn3.fansly.com/new/1/2/media-1/segment-3.ts"
    assert sm.is_signed_cdn_forbidden(forbidden(segment)) is False
    assert sm.is_signed_cdn_forbidden(forbidden(link, status=429)) is False
    api = "https://apiv3.fansly.com/api/v1/post?ids=1&Policy=a&Signature=b&Key-Pair-Id=c"
    assert sm.is_signed_cdn_forbidden(forbidden(api)) is False
