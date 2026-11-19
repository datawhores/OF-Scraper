"""Fansly: what a refused link costs in requests, through the real API and
address code (sites/fansly/api.py ``get_json``, sites/fansly/address.py).

A fake session answers ``account/media`` and the one-byte CDN tries, and
counts every request. Downloads themselves are simulated: a file's link is
refused when its range is refused by the CDN or the file is deleted. The
addresses are documentation ranges (RFC 5737).
"""

import asyncio
import contextlib
import copy
import gc
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import aiohttp
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.utils.refresh as refresh
from ofscraper.sites.fansly import address, api

from test_fansly_fetch_ahead import NEW, OLD, account_media, make_ele, scan_link


class Response:
    def __init__(self, data=None):
        self._data = data

    async def json_(self):
        return copy.deepcopy(self._data)


class Session:
    """``account/media`` answers each id with ``answer(n)`` (None leaves it
    out); the CDN refuses links signed for ``cdn_refused`` and the files in
    ``deleted``. Every request is counted."""

    def __init__(self, answer, cdn_refused=(), deleted=()):
        self.answer = answer
        self.cdn_refused = set(cdn_refused)
        self.deleted = set(deleted)
        self.api_calls = []
        self.probes = 0
        self.dns_cleared = 0
        self.fail = 0  # API calls still to fail
        self.down = None  # a function: True while the API fails
        self.failed = 0

    def clear_dns_cache(self):
        self.dns_cleared += 1

    def requests(self):
        return len(self.api_calls) + self.probes

    def cdn_ok(self, url):
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        return address._range(url) not in self.cdn_refused and name not in self.deleted

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        if "apiv3.fansly.com" in url:
            if self.fail or (self.down and self.down()):
                self.fail = max(0, self.fail - 1)
                self.failed += 1
                raise RuntimeError("503")
            ids = parse_qs(urlsplit(url).query)["ids"][0].split(",")
            self.api_calls.append(ids)
            items = [self.answer(int(i) - 1000) for i in ids]
            yield Response({"success": True, "response": [x for x in items if x]})
            return
        self.probes += 1
        if not self.cdn_ok(url):
            info = aiohttp.RequestInfo(URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url))
            raise aiohttp.ClientResponseError(info, (), status=403)
        yield Response()


@pytest.fixture
def world(monkeypatch):
    state = SimpleNamespace(session=None)

    @contextlib.asynccontextmanager
    async def session(**kwargs):
        yield state.session

    address.reset()
    refresh.fansly_refresher.reset()
    # one of the scan's links was tried on the CDN before the address changed
    scan_link(OLD)
    monkeypatch.setattr(refresh, "FANSLY_ASK_WAIT", 0)
    # files don't wait a pause out, unless a test says so
    monkeypatch.setattr(refresh, "PAUSE_WAITS", 0, raising=False)
    monkeypatch.setattr(
        refresh.manager, "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=session)),
    )
    yield state
    address.reset()
    refresh.fansly_refresher.reset()


def queue(count, start=0, signed_for=OLD):
    # each file in a post of its own
    items = [make_ele(n, signed_for, post=5000 + n) for n in range(start, start + count)]
    refresh.fansly_refresher.expect(items)
    return items


async def download(session, ele, refused):
    """The download loop's steps for one file; ``refused`` collects the
    files whose download got a 403."""
    await refresh.fresh_before_download(ele)
    ok = session.cdn_ok(ele.url)
    if not ok:
        refused.append(ele)
        ok = await refresh.refresh_media_link(ele, link=ele.url) and session.cdn_ok(ele.url)
    refresh.fansly_refresher.done(ele)
    return ok


def run(session, items):
    refused = []

    async def go():
        return [await download(session, ele, refused) for ele in items]

    return asyncio.run(go()), refused


def test_three_stuck_files_cost_no_more_requests_than_asking_for_each(world):
    # the address changed; Fansly keeps answering with its cached links
    world.session = Session(lambda n: account_media(n, OLD, "old"), cdn_refused={OLD})
    results, _ = run(world.session, queue(3))
    assert results == [False, False, False]
    # asking for each file alone: FANSLY_ASKS calls per file
    assert world.session.requests() <= 3 * refresh.FANSLY_ASKS
    # the cached answers don't move the API address
    assert world.session.dns_cleared == 0


def test_a_deleted_file_costs_one_probe_and_moves_nothing(world):
    world.session = Session(
        lambda n: None if n == 0 else account_media(n, OLD, "again"), deleted={"0.png"}
    )
    first, second, third = queue(3)
    others = (second.url, third.url)
    results, _ = run(world.session, [first])
    assert results == [False]
    # one probe of another link of the range: accepted, so this file only
    assert world.session.probes == 1
    assert world.session.api_calls == [["1000"]]
    assert world.session.dns_cleared == 0 and address._steered == {}
    assert not address.is_refused(second.url)
    assert (second.url, third.url) == others


def test_after_a_batch_with_cached_links_a_later_batch_still_works(world):
    calls = SimpleNamespace(cached=True)

    def answer(n):
        if calls.cached:
            return account_media(n, OLD, "old")
        return account_media(n, NEW, "new")

    world.session = Session(answer, cdn_refused={OLD})
    first = queue(3)
    results, _ = run(world.session, first[:1])
    assert results == [False]
    batch_calls = len(world.session.api_calls)

    # Fansly now signs new links; a later chunk is queued with old links
    calls.cached = False
    later = queue(3, start=3)
    results, refused = run(world.session, later)
    assert results == [True, True, True]
    # one shared call gave the whole later chunk new links before download
    assert refused == []
    new_calls = world.session.api_calls[batch_calls:]
    assert len(new_calls) == 1
    assert {"1003", "1004", "1005"} <= set(new_calls[0])
    assert all(address._range(ele.url) == NEW for ele in later)


def new_signature(session, signed_for):
    """Answers with a new signature on every call, signed for the range
    ``signed_for(session)`` gives."""

    def answer(n):
        return account_media(n, signed_for(session), f"call{len(session.api_calls)}")

    return answer


def shared(session):
    return [call for call in session.api_calls if len(call) > 1]


def alone(session):
    return [call for call in session.api_calls if len(call) == 1]


def test_788_files_after_an_address_change_cost_eight_calls(world):
    world.session = Session(lambda n: account_media(n, NEW, "new"), cdn_refused={OLD})
    results, refused = run(world.session, queue(788))
    assert all(results)
    assert len(refused) == 1
    # 100 ids a call, the most one call answers
    assert len(world.session.api_calls) == 8
    assert world.session.dns_cleared == 0


def test_deleted_files_side_by_side_make_no_shared_call(world):
    # the range is fine; the files of posts 0 and 1 are gone
    s = world.session = Session(None, deleted={"0.png", "1.png"})
    s.answer = new_signature(s, lambda s: OLD)
    items = queue(40)
    results, _ = run(s, items)
    assert results == [False, False] + [True] * 38
    assert shared(s) == []
    assert s.api_calls == [["1000"], ["1001"]]
    assert s.dns_cleared == 0 and address._steered == {}


def test_the_files_of_one_deleted_post_are_not_taken_for_a_dead_range(world):
    s = world.session = Session(None, deleted={"0.png", "1.png", "2.png"})
    s.answer = new_signature(s, lambda s: OLD)
    gone = [make_ele(n, post=7000) for n in range(3)]
    rest = [make_ele(n, post=5000 + n) for n in range(3, 10)]
    refresh.fansly_refresher.expect(gone + rest)
    results, _ = run(s, gone + rest)
    assert results == [False] * 3 + [True] * 7
    assert shared(s) == []
    assert not address.is_refused(rest[0].url)


def test_a_deleted_post_with_nothing_else_waiting_marks_no_range(world):
    # only the post's own files are waiting: none of them can show that the
    # range is refused
    s = world.session = Session(None, deleted={"0.png", "1.png", "2.png"})
    s.answer = new_signature(s, lambda s: OLD)
    gone = [make_ele(n, post=7000) for n in range(3)]
    refresh.fansly_refresher.expect(gone)
    results, _ = run(s, gone)
    assert results == [False] * 3
    assert shared(s) == []
    assert not address.is_refused(gone[0].url)
    assert s.dns_cleared == 0 and address._steered == {}


def test_two_deleted_posts_with_nothing_else_waiting_mark_no_range(world):
    # each post's files are refused, and so is the other post's: the link the
    # CDN accepted during the scan still is, so the range is fine
    s = world.session = Session(None, deleted={f"{n}.png" for n in range(6)})
    s.answer = new_signature(s, lambda s: OLD)
    gone = [make_ele(n, post=7000 + n // 3) for n in range(6)]
    refresh.fansly_refresher.expect(gone)
    results, _ = run(s, gone)
    assert results == [False] * 6
    assert shared(s) == []
    assert not address.is_refused(gone[0].url)
    assert s.dns_cleared == 0 and address._steered == {}


def test_one_post_waiting_after_an_address_change_shares_one_call(world):
    s = world.session = Session(lambda n: account_media(n, NEW, "new"), cdn_refused={OLD})
    items = [make_ele(n, post=7000) for n in range(40)]
    refresh.fansly_refresher.expect(items)
    results, refused = run(s, items)
    assert all(results)
    assert len(refused) == 1
    assert len(s.api_calls) == 1 and len(s.api_calls[0]) == 40


def test_with_no_link_tried_before_a_files_new_link_shows_the_change(world):
    # nothing was tried on the CDN for the old range: the first file asks on
    # its own, its new link is signed for another range and accepted, and
    # the rest share one call
    address.reset()
    s = world.session = Session(lambda n: account_media(n, NEW, "new"), cdn_refused={OLD})
    items = [make_ele(n, post=7000) for n in range(40)]
    refresh.fansly_refresher.expect(items)
    results, refused = run(s, items)
    assert all(results)
    assert len(refused) == 1
    assert [len(call) for call in s.api_calls] == [1, 39]


def test_a_range_whose_kept_link_was_just_accepted_is_not_marked_by_a_new_link(world):
    # file 0 is refused for a reason of its own, and its new link is signed
    # for another range the CDN accepts: the old range's kept link was
    # accepted a moment ago, so the old range is fine
    scan_link(NEW)
    s = world.session = Session(lambda n: account_media(n, NEW, "new"), deleted={"0.png"})
    items = queue(40)
    results, _ = run(s, items)
    assert results == [False] + [True] * 39
    assert not address.is_refused(items[5].url)
    assert shared(s) == []
    assert alone(s) == [["1000"]]


def test_a_range_marked_wrongly_costs_one_shared_call_and_is_cleared(world):
    # the file of the only link kept to confirm the refusal is deleted too
    s = world.session = Session(None, deleted={"0.png", "9999.png"})
    s.answer = new_signature(s, lambda s: OLD)
    items = queue(40)
    results, _ = run(s, items)
    assert results == [False] + [True] * 39
    # the shared call's new links are tried on the CDN: accepted, mark gone
    assert len(shared(s)) == 1
    assert address.is_accepted(items[5].url)
    assert alone(s) == []
    assert s.dns_cleared == 0


def test_one_kept_link_deleted_too_marks_no_range_while_another_is_accepted(world):
    # two links of the range were accepted during the scan; the file of the
    # newest is deleted, and so is the file being downloaded
    scan_link(OLD, n=9998)
    s = world.session = Session(None, deleted={"0.png", "9998.png"})
    s.answer = new_signature(s, lambda s: OLD)
    items = queue(40)
    results, _ = run(s, items)
    assert results == [False] + [True] * 39
    assert shared(s) == []
    assert alone(s) == [["1000"]]
    assert not address.is_refused(items[5].url)
    assert s.dns_cleared == 0


def test_files_wait_out_a_burst_of_failed_calls_instead_of_failing(world, monkeypatch):
    # the address changed, and the API fails for the first minute after it
    clock = SimpleNamespace(now=1000.0)
    real_sleep = asyncio.sleep

    async def sleep(seconds, *args):
        clock.now += seconds
        await real_sleep(0)

    monkeypatch.setattr(refresh, "_clock", lambda: clock.now)
    monkeypatch.setattr(refresh.asyncio, "sleep", sleep)
    monkeypatch.setattr(refresh, "PAUSE_WAITS", 2, raising=False)
    s = world.session = Session(lambda n: account_media(n, NEW, "new"), cdn_refused={OLD})
    s.down = lambda: clock.now < 1060
    results, _ = run(s, queue(60))
    # the files whose calls failed are lost; the rest wait and share one call
    assert results.count(False) <= refresh.CALL_FAILURES
    assert alone(s) == []
    assert len(shared(s)) == 1
    assert 1120 <= clock.now < 1130


def test_an_address_that_changes_back_costs_one_more_shared_call(world):
    """VPN off at file 0 (the CDN refuses OLD, Fansly signs NEW), back on at
    file 20 (the CDN refuses NEW, Fansly signs OLD again)."""
    s = world.session = Session(None, cdn_refused={OLD})
    phase = SimpleNamespace(back=False)
    s.answer = new_signature(s, lambda s: OLD if phase.back else NEW)
    items = queue(60)

    async def go():
        refused, out, before = [], [], None
        for number, ele in enumerate(items):
            if number == 20:
                phase.back = True
                s.cdn_refused = {NEW}
                before = len(s.api_calls)
            out.append(await download(s, ele, refused))
        return out, before

    results, before = asyncio.run(go())
    assert all(results)
    assert before == 1
    assert len(s.api_calls) - before == 1
    assert s.dns_cleared == 0


def test_new_links_signed_for_the_refused_range_move_the_api_address_once(world):
    # the API still sees the old address (#683) until its next address is used
    s = world.session = Session(None, cdn_refused={OLD})
    s.answer = new_signature(s, lambda s: OLD if s.dns_cleared == 0 else NEW)
    results, refused = run(s, queue(20))
    assert all(results)
    assert len(refused) == 1
    assert len(s.api_calls) == 2
    assert s.dns_cleared == 1


def test_a_range_fansly_keeps_signing_for_ends_the_shared_calls(world):
    s = world.session = Session(None, cdn_refused={OLD})
    s.answer = new_signature(s, lambda s: OLD)
    items = queue(10)
    results, _ = run(s, items)
    assert results == [False] * 10
    # one shared call that asks every API address, then one call per file,
    # as without fetching ahead
    assert len(shared(s)) == api.ADDRESS_ASKS
    assert s.dns_cleared == api.ADDRESS_ASKS - 1
    assert len(alone(s)) <= len(items)


def test_every_api_address_is_asked_before_a_range_is_given_up(world):
    # only the last of the API host's addresses sees the address the
    # downloads leave from
    s = world.session = Session(None, cdn_refused={OLD})
    s.answer = new_signature(s, lambda s: OLD if s.dns_cleared < 3 else NEW)
    results, refused = run(s, queue(20))
    assert all(results)
    assert len(refused) == 1
    assert len(s.api_calls) == 4
    assert s.dns_cleared == 3


@pytest.mark.parametrize("working", [1, 2, 3])
def test_asks_that_fail_on_the_way_dont_start_the_addresses_again(world, working):
    # a rate limit: after every one, two or three API calls that work, two
    # fail (an ask and its second try), so no shared call gets through all
    # its asks
    s = world.session = Session(None, cdn_refused={OLD})
    s.answer = new_signature(s, lambda s: OLD)
    s.down = lambda: (len(s.api_calls) + s.failed) % (working + 2) >= working
    items = queue(60)
    results, _ = run(s, items)
    assert results == [False] * 60
    # the asks of all the shared calls together are one per API address
    assert len(shared(s)) == api.ADDRESS_ASKS
    assert s.dns_cleared == api.ADDRESS_ASKS - 1
    assert len(alone(s)) <= len(items)
    assert len(s.api_calls) + s.failed <= 2 * (len(items) + api.ADDRESS_ASKS)


def test_a_range_given_up_is_counted_from_the_start_once_its_links_are_accepted(world):
    # refused from two addresses, accepted from the third; much later
    # Fansly signs for the refused range again
    s = world.session = Session(None, cdn_refused={OLD})
    phase = SimpleNamespace(again=False)
    s.answer = new_signature(
        s, lambda s: OLD if phase.again or s.dns_cleared < 2 else NEW
    )
    items = queue(40)

    async def go():
        refused, out = [], []
        for number, ele in enumerate(items):
            if number == 20:
                phase.again = True
                s.cdn_refused = {OLD, NEW}
                before = len(shared(s)), s.dns_cleared
            out.append(await download(s, ele, refused))
        return out, before

    results, (calls, moves) = asyncio.run(go())
    assert all(results[:20])
    assert (calls, moves) == (3, 2)
    # the two refused asks from before don't count: every address is asked
    assert len(shared(s)) - calls == api.ADDRESS_ASKS
    assert s.dns_cleared - moves == api.ADDRESS_ASKS - 1


THIRD = "203.0.113.0/24"


def test_addresses_that_sign_for_two_refused_ranges_in_turn_end_the_shared_calls(world):
    # some API addresses see one address of the computer and the others
    # another (IPv4 and IPv6), and the CDN refuses both
    s = world.session = Session(None, cdn_refused={OLD, THIRD})
    s.answer = new_signature(s, lambda s: OLD if s.dns_cleared % 2 == 0 else THIRD)
    items = queue(60)
    results, _ = run(s, items)
    assert results == [False] * 60
    assert len(shared(s)) == api.ADDRESS_ASKS
    assert s.dns_cleared == api.ADDRESS_ASKS - 1
    assert len(alone(s)) <= len(items)


def test_an_answer_without_the_media_leaves_the_count_alone(world):
    # every other answer leaves the media out, which says nothing about
    # the address
    s = world.session = Session(None, cdn_refused={OLD})
    new = new_signature(s, lambda s: OLD)
    s.answer = lambda n: new(n) if len(s.api_calls) % 2 else None
    items = queue(60)
    results, _ = run(s, items)
    assert results == [False] * 60
    assert len(shared(s)) <= 2 * api.ADDRESS_ASKS
    assert s.dns_cleared == api.ADDRESS_ASKS - 1


def four_refused_asks_and_a_failed_one(s):
    """The first shared call: four asks with refused links, then one that
    fails with its second try."""
    attempts = SimpleNamespace(made=-1)

    def down():
        attempts.made += 1
        return attempts.made in (4, 5)

    s.down = down


def test_refused_asks_are_counted_only_for_a_while(world, monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(refresh, "_clock", lambda: clock.now)
    s = world.session = Session(None, cdn_refused={OLD})
    phase = SimpleNamespace(later=None)
    # much later, the API address four moves on signs for the right range
    s.answer = new_signature(
        s, lambda s: OLD if phase.later is None or s.dns_cleared < phase.later + 4 else NEW
    )
    four_refused_asks_and_a_failed_one(s)
    items = queue(40)

    async def go():
        refused, out = [], []
        for number, ele in enumerate(items):
            if number == 1:
                phase.later = s.dns_cleared
                clock.now += refresh.REFUSED_ASKS_KEPT + 1
            out.append(await download(s, ele, refused))
        return out

    # the four asks from before don't count any more: every address is asked
    assert asyncio.run(go()) == [False] + [True] * 39


def test_an_address_change_starts_the_count_of_refused_asks_again(world):
    scan_link(NEW)
    s = world.session = Session(None, cdn_refused={OLD})
    phase = SimpleNamespace(changed=None)

    def signed_for(s):
        if phase.changed is None:
            return OLD
        return NEW if s.dns_cleared < phase.changed + 4 else THIRD

    s.answer = new_signature(s, signed_for)
    four_refused_asks_and_a_failed_one(s)
    items = queue(1) + queue(20, start=1, signed_for=NEW)

    async def go():
        refused, out = [], []
        for number, ele in enumerate(items):
            if number == 1:
                # the address downloads leave from changes; only the fifth
                # API address asked signs for it
                phase.changed = s.dns_cleared
                s.cdn_refused = {OLD, NEW}
            out.append(await download(s, ele, refused))
        return out

    assert asyncio.run(go()) == [False] + [True] * 20


def test_an_address_change_a_files_own_link_shows_starts_the_count_again(world):
    # no link of the range the later files are signed for was tried, so
    # the first of them asks on its own and its new link shows the change
    s = world.session = Session(None, cdn_refused={OLD})
    phase = SimpleNamespace(calls=None)

    def signed_for(s):
        if phase.calls is None:
            return OLD
        # that file's own ask, then only the fifth shared ask, are signed
        # for the address downloads leave from now
        return NEW if 1 < len(s.api_calls) - phase.calls <= 5 else THIRD

    s.answer = new_signature(s, signed_for)
    four_refused_asks_and_a_failed_one(s)
    items = queue(1) + queue(20, start=1, signed_for=NEW)

    async def go():
        refused, out = [], []
        for number, ele in enumerate(items):
            if number == 1:
                phase.calls = len(s.api_calls)
                s.cdn_refused = {OLD, NEW}
            out.append(await download(s, ele, refused))
        return out

    assert asyncio.run(go()) == [False] + [True] * 20
    assert [len(call) for call in s.api_calls[phase.calls:]] == [1] + [19] * 5


def test_a_shared_call_that_fails_twice_is_made_again_for_the_next_file(world):
    s = world.session = Session(lambda n: account_media(n, NEW, "new"), cdn_refused={OLD})
    s.fail = 2
    results, _ = run(s, queue(300))
    assert results == [False] + [True] * 299
    assert s.failed == 2
    assert len(s.api_calls) == 3


@pytest.mark.parametrize(
    "junk",
    ["not an item", {"id": "1000", "media": "not a media"}, {"id": "1000", "media": {"id": 5}}],
    ids=["not-a-dict", "bad-media", "other-media"],
)
def test_a_malformed_answer_fails_the_refresh_without_raising(world, junk):
    world.session = Session(lambda n: junk, cdn_refused={OLD})
    results, _ = run(world.session, queue(3))
    assert results == [False, False, False]


def test_an_error_after_its_waiter_was_cancelled_is_not_left_for_the_loop(world, monkeypatch):
    first = make_ele(0)
    refresh.fansly_refresher.expect([first])
    reported = []

    async def go():
        gate = asyncio.Event()

        async def broken(ele, link, before):
            await gate.wait()
            raise RuntimeError("boom")

        monkeypatch.setattr(refresh.fansly_refresher, "_fresh", broken)
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, context: reported.append(context.get("message"))
        )
        waiter = asyncio.ensure_future(refresh.fansly_refresher.fresh(first, first.url))
        await asyncio.sleep(0.01)
        waiter.cancel()
        await asyncio.sleep(0)
        gate.set()
        await asyncio.sleep(0.05)
        gc.collect()

    asyncio.run(go())
    gc.collect()
    assert reported == []
    # and a waiter that is still there gets the reason, not the error
    assert "boom" in asyncio.run(refresh.fansly_refresher.fresh(first, first.url))
