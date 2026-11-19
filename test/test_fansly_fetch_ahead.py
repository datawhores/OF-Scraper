"""Fansly: one refused link fetches new links for every waiting file signed
for the same address range.

After the address downloads leave from changes (a VPN switch), the CDN
refuses every link signed before it. Asking per file costs one
``account/media`` call each, at about ten calls a minute; one call carries up
to ``ACCOUNT_MEDIA_BATCH`` ids.

No request is sent anywhere: ``account/media`` is faked. The addresses are
documentation ranges (RFC 5737).
"""

import asyncio
import time
import base64
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.utils.refresh as refresh
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.sites.fansly import address, api

OLD, NEW = "192.0.2.0/24", "198.51.100.0/24"


def link(n, signed_for, tag, until=1900000000):
    if signed_for is None:
        query = f"Expires=1900000000&Signature=sig-{tag}&Key-Pair-Id=k"
    else:
        policy = {
            "Statement": [
                {
                    "Resource": f"https://cdn3.fansly.com/100/{n}.png",
                    "Condition": {
                        "DateLessThan": {"AWS:EpochTime": until},
                        "IpAddress": {"AWS:SourceIp": signed_for},
                    },
                }
            ]
        }
        encoded = base64.b64encode(json.dumps(policy).encode()).decode()
        encoded = encoded.replace("+", "-").replace("=", "_").replace("/", "~")
        query = f"Policy={encoded}&Signature=sig-{tag}&Key-Pair-Id=k"
    return f"https://cdn3.fansly.com/100/{n}.png?{query}"


def account_media(n, signed_for, tag):
    """An accountMedia answer for image ``n``."""
    return {
        "id": str(1000 + n),
        "media": {
            "id": str(2000 + n),
            "mimetype": "image/png",
            "locations": [{"locationId": "1", "location": link(n, signed_for, tag)}],
            "variants": [],
        },
    }


def make_ele(n, signed_for=OLD, tag="old", post=100000000000000005):
    item = account_media(n, signed_for, tag)
    raw = item["media"]
    media = {
        "id": int(raw["id"]),
        "type": "photo",
        "canView": True,
        "files": {"full": {"url": raw["locations"][0]["location"]}},
        "fansly": {
            "accountMediaId": item["id"],
            "mediaId": raw["id"],
            "isPreview": False,
            "media": raw,
        },
    }
    post = Post(
        {"id": post, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        100000000000000002,
        "a-creator",
        responsetype="timeline",
    )
    return Media(media, 0, post)


def scan_link(signed_for, n=9999):
    """The link of the scan that was tried on the CDN, and accepted, before
    the address changed."""
    address._keep(signed_for, link(n, signed_for, "scan"), True)


@pytest.fixture
def fansly(monkeypatch):
    """``account/media``: each id answered with a link signed for ``NEW``
    (or as ``answer`` says), every call recorded."""
    calls = []
    state = SimpleNamespace(calls=calls, answer=None, error=None, gate=None, probes=[])

    @asynccontextmanager
    async def session(**kwargs):
        yield "session"

    async def cdn_accepts(c, url):
        # the CDN refuses every link signed for the old range
        state.probes.append(url)
        return address._range(url) != OLD

    async def fake_account_media(c, ids, asks=None):
        calls.append([str(i) for i in ids])
        if state.gate is not None:
            await state.gate.wait()
        if state.error:
            raise state.error
        out = []
        for i in ids:
            n = int(i) - 1000
            made = (state.answer or (lambda n: account_media(n, NEW, f"new{len(calls)}")))(n)
            if made is not None:
                out.append(made)
        return out

    async def no_sleep(seconds):
        pass

    address.reset()
    refresh.fansly_refresher.reset()
    scan_link(OLD)
    monkeypatch.setattr(refresh.fansly_api, "account_media", fake_account_media)
    monkeypatch.setattr(refresh, "FANSLY_ASK_WAIT", 0)
    # files don't wait a pause out, unless a test says so
    monkeypatch.setattr(refresh, "PAUSE_WAITS", 0, raising=False)
    monkeypatch.setattr(address, "_cdn_accepts", cdn_accepts)
    monkeypatch.setattr(
        refresh.manager, "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=session)),
    )
    yield state
    address.reset()
    refresh.fansly_refresher.reset()


def waiting(count, **kwargs):
    # each file in a post of its own
    items = [make_ele(n, **{"post": 100000000000000100 + n, **kwargs}) for n in range(count)]
    refresh.fansly_refresher.expect(items)
    return items


async def download_all(items):
    """What the download loop does with each item: the check before the
    download, a 403 when its link is still signed for the old range (the
    CDN refuses it), then ``done``."""
    for ele in items:
        await refresh.fresh_before_download(ele)
        if address._range(ele.url) == OLD:
            assert await refresh.refresh_media_link(ele, link=ele.url)
        refresh.fansly_refresher.done(ele)


def test_one_refusal_among_300_waiting_files_makes_two_calls(fansly):
    items = waiting(300)
    asyncio.run(download_all(items))
    assert [len(call) for call in fansly.calls] == [
        api.ACCOUNT_MEDIA_BATCH,
        300 - api.ACCOUNT_MEDIA_BATCH,
    ]
    assert all(address._range(ele.url) == NEW for ele in items)


def test_a_file_fetched_ahead_downloads_without_a_call_of_its_own(fansly):
    first, second = waiting(2)

    async def go():
        assert await refresh.refresh_media_link(first, link=first.url)
        refresh.fansly_refresher.done(first)
        assert address._range(second.url) == NEW
        await refresh.fresh_before_download(second)

    asyncio.run(go())
    assert fansly.calls == [[first.media["fansly"]["accountMediaId"], "1001"]]


def test_files_signed_for_a_range_that_was_not_refused_are_left_alone(fansly):
    refused = make_ele(0)
    fine = make_ele(1, signed_for=NEW, tag="fine")
    refresh.fansly_refresher.expect([refused, fine])
    before = fine.url
    assert asyncio.run(refresh.refresh_media_link(refused, link=refused.url))
    assert fansly.calls == [["1000"]]
    assert fine.url == before


def test_two_downloads_refused_together_share_one_call(fansly):
    first, second = waiting(2)

    async def go():
        fansly.gate = asyncio.Event()
        one = asyncio.ensure_future(refresh.refresh_media_link(first, link=first.url))
        await asyncio.sleep(0)
        two = asyncio.ensure_future(refresh.refresh_media_link(second, link=second.url))
        await asyncio.sleep(0)
        fansly.gate.set()
        return await asyncio.gather(one, two)

    assert asyncio.run(go()) == [True, True]
    assert len(fansly.calls) == 1


def test_the_same_link_for_one_file_sends_it_alone_to_the_old_loop(fansly):
    stuck, other = waiting(2)

    def answer(n):
        # file 0: the same link every time, until the old loop's last ask
        if n == 0 and len(fansly.calls) < refresh.FANSLY_ASKS:
            return account_media(0, OLD, "old")
        return account_media(n, NEW, f"new{len(fansly.calls)}")

    fansly.answer = answer
    assert asyncio.run(refresh.refresh_media_link(stuck, link=stuck.url))
    # the shared call, then the old loop's remaining asks, for file 0 only
    assert fansly.calls == [["1000", "1001"]] + [["1000"]] * (refresh.FANSLY_ASKS - 1)
    assert address._range(other.url) == NEW
    assert address._range(stuck.url) == NEW


def test_a_failed_call_is_tried_once_more_and_the_others_stay_waiting(fansly, monkeypatch):
    waits = []
    real_sleep = asyncio.sleep

    async def sleep(seconds, *args):
        waits.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(refresh, "FANSLY_ASK_WAIT", 7)
    monkeypatch.setattr(refresh.asyncio, "sleep", sleep)
    first, second = waiting(2)
    fansly.error = RuntimeError("503")
    before = second.url
    assert asyncio.run(refresh.refresh_media_link(first, link=first.url)) is False
    assert second.url == before
    assert len(fansly.calls) == 2  # the call and its one retry,
    assert waits == [7]  # after a wait: a rate limit would fail a retry at once
    # the waiting file isn't left to ask alone: the next shared call, before
    # its download, is for it too
    fansly.error = None
    asyncio.run(refresh.fresh_before_download(second))
    assert len(fansly.calls) == 3 and "1001" in fansly.calls[2]
    assert address._range(second.url) == NEW


def test_after_failed_shared_calls_in_a_row_files_ask_on_their_own(fansly):
    items = waiting(5)
    fansly.error = RuntimeError("503")

    async def refused(some):
        return [await refresh.refresh_media_link(ele, link=ele.url) for ele in some]

    failing = items[: refresh.CALL_FAILURES]
    assert asyncio.run(refused(failing)) == [False] * refresh.CALL_FAILURES
    assert len(fansly.calls) == 2 * refresh.CALL_FAILURES
    fansly.error = None
    fansly.calls.clear()
    # no shared call before the download, one call for this file alone after
    following = items[refresh.CALL_FAILURES]
    asyncio.run(refresh.fresh_before_download(following))
    assert fansly.calls == []
    assert asyncio.run(refused([following])) == [True]
    assert fansly.calls == [[following.media["fansly"]["accountMediaId"]]]
    assert address._range(items[-1].url) == OLD


def test_fetching_ahead_starts_again_after_its_pause(fansly, monkeypatch):
    # a burst of rate limiting early in the run, an address change later
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(refresh, "_clock", lambda: clock.now)
    items = waiting(8)
    fansly.error = RuntimeError("429")

    async def refused(some):
        return [await refresh.refresh_media_link(ele, link=ele.url) for ele in some]

    asyncio.run(refused(items[: refresh.CALL_FAILURES]))
    fansly.error = None
    fansly.calls.clear()
    clock.now += refresh.FETCH_AHEAD_PAUSE - 1
    asyncio.run(refresh.fresh_before_download(items[3]))
    assert fansly.calls == []
    clock.now += 2
    # one shared call for every file still waiting
    asyncio.run(refresh.fresh_before_download(items[3]))
    assert len(fansly.calls) == 1 and len(fansly.calls[0]) == 8
    assert {address._range(ele.url) for ele in items} == {NEW}


def test_one_more_failed_call_after_the_pause_pauses_again(fansly, monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(refresh, "_clock", lambda: clock.now)
    items = waiting(8)
    fansly.error = RuntimeError("429")

    async def refused(some):
        return [await refresh.refresh_media_link(ele, link=ele.url) for ele in some]

    asyncio.run(refused(items[: refresh.CALL_FAILURES]))
    clock.now += refresh.FETCH_AHEAD_PAUSE + 1
    fansly.calls.clear()
    asyncio.run(refresh.fresh_before_download(items[3]))
    assert len(fansly.calls) == 2  # the call and its retry
    asyncio.run(refresh.fresh_before_download(items[4]))
    assert len(fansly.calls) == 2


def test_a_cancelled_waiter_does_not_cancel_the_call(fansly):
    first, second = waiting(2)

    async def go():
        fansly.gate = asyncio.Event()
        one = asyncio.ensure_future(refresh.refresh_media_link(first, link=first.url))
        await asyncio.sleep(0)
        two = asyncio.ensure_future(refresh.refresh_media_link(second, link=second.url))
        await asyncio.sleep(0)
        one.cancel()
        await asyncio.sleep(0)
        fansly.gate.set()
        return await two

    assert asyncio.run(go()) is True
    assert len(fansly.calls) == 1
    assert address._range(first.url) == NEW


def test_a_link_without_a_range_takes_the_per_file_path(fansly):
    plain = make_ele(0, signed_for=None)
    other = make_ele(1)
    refresh.fansly_refresher.expect([plain, other])
    other_before = other.url
    assert asyncio.run(refresh.refresh_media_link(plain, link=plain.url))
    assert fansly.calls == [["1000"]]
    assert other.url == other_before
    assert not address.is_refused(other.url)


def test_a_finished_file_is_never_fetched_again(fansly):
    first, second, third = waiting(3)
    refresh.fansly_refresher.done(second)
    assert asyncio.run(refresh.refresh_media_link(first, link=first.url))
    assert fansly.calls == [["1000", "1002"]]


def test_onlyfans_items_never_reach_the_refresher(fansly):
    of_item = SimpleNamespace(media={"files": {}}, url=link(9, OLD, "old"))
    refresh.fansly_refresher.expect([of_item])
    assert refresh.fansly_refresher._waiting == {}
    address.refused(of_item.url)
    asyncio.run(refresh.fresh_before_download(of_item))
    assert fansly.calls == []


def test_a_confirmed_refusal_replaces_what_the_probe_learned(fansly):
    old = link(0, OLD, "old")
    address._accepted[OLD] = True
    address.refused(old)
    assert address.is_refused(old) and not address.is_accepted(old)
    assert address._accepted == {OLD: False}
    # one fact: forgetting the refused ranges forgets this one, and the next
    # link signed for it is tried on the CDN again
    address.forget_refused()
    assert not address.is_refused(old) and not address.is_accepted(old)
    address.refused(old)
    # without a range, or never seen: nothing changes
    address.refused(link(1, None, "plain"))
    assert not address.is_refused(link(1, None, "plain"))
    assert not address.is_refused(link(2, NEW, "x"))
    assert not address.is_refused(None)


def test_a_new_link_the_cdn_accepts_clears_the_refusal(fansly, monkeypatch):
    old = link(0, OLD, "old")
    address.refused(old)

    async def accepts(c, url):
        return True

    monkeypatch.setattr(address, "_cdn_accepts", accepts)
    assert asyncio.run(address.try_link(None, link(1, OLD, "new"))) is True
    assert not address.is_refused(old) and address.is_accepted(old)
    # a link without a range says nothing
    assert asyncio.run(address.try_link(None, link(1, None, "plain"))) is None


def test_the_links_tried_again_are_ones_the_cdn_accepted_for_other_files(fansly):
    refused = link(1, OLD, "old")
    assert address.accepted_links(refused) == [link(9999, OLD, "scan")]
    # nothing kept for the range
    assert address.accepted_links(link(1, NEW, "old")) == []
    # two are kept, the newest first; a file is kept once, and a third
    # replaces the oldest
    scan_link(OLD, n=8)
    scan_link(OLD, n=8)
    assert address.accepted_links(refused) == [link(8, OLD, "scan"), link(9999, OLD, "scan")]
    scan_link(OLD, n=9)
    assert address.accepted_links(refused) == [link(9, OLD, "scan"), link(8, OLD, "scan")]
    # a kept link that has run out would be refused whatever the range
    address._keep(OLD, link(2, OLD, "scan", until=int(time.time()) + 5), True)
    assert address.accepted_links(refused) == [link(9, OLD, "scan")]
    # this file's own link says nothing about it
    address._keep(OLD, link(1, OLD, "scan"), True)
    assert address.accepted_links(refused) == [link(9, OLD, "scan")]
    # a kept link whose file was deleted is dropped
    address.gone(link(9, OLD, "scan"))
    assert address.accepted_links(refused) == []
    # a refusal of the range drops them all
    scan_link(OLD)
    address.refused(refused)
    assert address.accepted_links(refused) == []


def test_a_range_is_refused_only_when_every_kept_link_is(fansly, monkeypatch):
    scan_link(OLD, n=9998)
    first, second = waiting(2)
    deleted = {"/100/9998.png"}

    async def cdn_accepts(c, url):
        fansly.probes.append(url)
        return refresh._path(url) not in deleted

    monkeypatch.setattr(address, "_cdn_accepts", cdn_accepts)
    confirmed, tried = asyncio.run(
        refresh.fansly_refresher._range_refused(first, first.url)
    )
    # the newest kept link is refused, the other one accepted: its file is
    # gone, the range is fine, and it is not tried again
    assert not confirmed
    assert fansly.probes == [link(9998, OLD, "scan"), link(9999, OLD, "scan")]
    assert address.accepted_links(first.url) == [link(9999, OLD, "scan")]
    # both refused: the range is
    scan_link(OLD, n=9998)
    deleted.add("/100/9999.png")
    confirmed, tried = asyncio.run(
        refresh.fansly_refresher._range_refused(second, second.url)
    )
    assert confirmed and len(tried) == 2


def test_files_wait_for_the_end_of_a_pause_then_share_a_call(fansly, monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    waits = []
    real_sleep = asyncio.sleep

    async def sleep(seconds, *args):
        waits.append(seconds)
        clock.now += seconds
        await real_sleep(0)

    monkeypatch.setattr(refresh, "_clock", lambda: clock.now)
    monkeypatch.setattr(refresh.asyncio, "sleep", sleep)
    monkeypatch.setattr(refresh, "PAUSE_WAITS", 1, raising=False)
    items = waiting(9)
    fansly.error = RuntimeError("429")

    async def refused(some):
        return [await refresh.refresh_media_link(ele, link=ele.url) for ele in some]

    asyncio.run(refused(items[: refresh.CALL_FAILURES]))
    fansly.error = None
    fansly.calls.clear()
    waits.clear()
    # the pause is waited out, then one call for every file still waiting
    asyncio.run(refresh.fresh_before_download(items[3]))
    assert len(waits) == 1 and waits[0] == pytest.approx(refresh.FETCH_AHEAD_PAUSE, abs=1)
    assert len(fansly.calls) == 1 and len(fansly.calls[0]) == 9
    assert {address._range(ele.url) for ele in items} == {NEW}

    # a second pause in a row is not waited out: the file asks on its own
    address.refused(link(0, NEW, "x"))
    later = waiting(4, signed_for=NEW)
    fansly.error = RuntimeError("429")
    asyncio.run(refused(later[: refresh.CALL_FAILURES]))
    asyncio.run(refused(later[: refresh.CALL_FAILURES]))
    waits.clear()
    fansly.calls.clear()
    asyncio.run(refresh.fresh_before_download(later[3]))
    assert waits == [] and fansly.calls == []


def test_the_url_of_a_refused_request_is_read_from_the_error():
    url = link(0, OLD, "old")
    info = aiohttp.RequestInfo(URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url))
    error = aiohttp.ClientResponseError(info, (), status=403)
    assert address._range(refresh.refused_url(error)) == OLD
    assert refresh.refused_url(RuntimeError("x")) is None
