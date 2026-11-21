"""An address of OnlyFans' file host that refuses good links is left (#620).

The host answers at several addresses. One refused every signed link while
the others took the same links, so some files of each run failed with a 403
and a second run got them. An address is left when the site still gives the
link it refused: a link that ran out is refused by every address (#462).
"""

import asyncio
import socket
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver
from yarl import URL

import ofscraper.managers.sessionmanager.refusing as refusing
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.sites.fansly.address as address

HOST = "cdn2.onlyfans.com"
SIGNING = "Policy=example&Signature=example&Key-Pair-Id=example"
REFUSES, TAKES = "127.0.0.1", "127.0.0.2"
QUIET = SimpleNamespace(debug=lambda *a: None, traceback_=lambda *a: None)


@pytest.fixture(autouse=True)
def _nothing_refused():
    refusing.reset()
    yield
    refusing.reset()


def _answers(*hosts):
    return [{"hostname": HOST, "host": h, "port": 443} for h in hosts]


def _hosts(answers):
    return [a["host"] for a in answers]


# ---- which addresses are left out -------------------------------------------


class _Transport:
    """A connection that, like one over TLS, no longer tells its other end
    once it is closed."""

    def __init__(self, peer=("192.0.2.1", 443)):
        self.peer = peer
        self.closed = False

    def get_extra_info(self, name):
        assert name == "peername"
        return None if self.closed else self.peer

    def close(self):
        self.closed = True


def _refusal(peer=("192.0.2.1", 443), host=HOST):
    """What the session's response remembers of a refusal."""
    return SimpleNamespace(
        came_over=_Transport(peer),
        came_from=peer[0] if peer else None,
        url=URL(f"https://{host}/files/a.jpg?{SIGNING}"),
    )


def test_nothing_is_left_out_before_a_refusal():
    answers = _answers("192.0.2.1", "192.0.2.2")
    assert refusing.without(HOST, answers) is answers


def test_the_address_that_refused_is_left_out_and_its_connection_closed():
    r = _refusal()
    assert refusing.leave(r) is True
    assert r.came_over.closed is True
    assert _hosts(refusing.without(HOST, _answers("192.0.2.1", "192.0.2.2"))) == [
        "192.0.2.2"
    ]


def test_an_address_already_left_changes_nothing_more():
    assert refusing.leave(_refusal()) is True
    assert refusing.times_left() == 1
    again = _refusal()
    assert refusing.leave(again) is False
    assert again.came_over.closed is True
    assert refusing.times_left() == 1


def test_a_refusal_whose_connection_is_closed_still_leaves_the_address():
    # a protected video's manifest is read through a session of its own,
    # closed by the time the site is asked whether the link is still good
    r = _refusal()
    r.came_over.close()
    assert refusing.leave(r) is True
    assert _hosts(refusing.without(HOST, _answers("192.0.2.1", "192.0.2.2"))) == [
        "192.0.2.2"
    ]


def test_a_connection_to_an_address_that_was_left_is_told_apart():
    assert refusing.goes_to_one_left(HOST, _Transport()) is False
    refusing.leave(_refusal())
    assert refusing.goes_to_one_left(HOST, _Transport()) is True
    assert refusing.goes_to_one_left(HOST, _Transport(("192.0.2.2", 443))) is False
    # the address was left for this host only
    assert refusing.goes_to_one_left("cdn3.onlyfans.com", _Transport()) is False
    # a closed connection, or none
    assert refusing.goes_to_one_left(HOST, _Transport(None)) is False
    assert refusing.goes_to_one_left(HOST, None) is False


def test_another_host_keeps_the_address():
    refusing.leave(_refusal())
    other = [
        {"hostname": "cdn3.onlyfans.com", "host": h, "port": 443}
        for h in ("192.0.2.1", "192.0.2.2")
    ]
    assert _hosts(refusing.without("cdn3.onlyfans.com", other)) == [
        "192.0.2.1", "192.0.2.2"
    ]


def test_when_every_address_refused_all_are_used_again():
    # the link ran out, or this machine's address changed: not the address
    refusing.leave(_refusal(("192.0.2.1", 443)))
    refusing.leave(_refusal(("192.0.2.2", 443)))
    answers = _answers("192.0.2.1", "192.0.2.2")
    assert refusing.without(HOST, answers) is answers
    # and the refusals are forgotten: one new refusal leaves out one address
    refusing.leave(_refusal(("192.0.2.2", 443)))
    assert _hosts(refusing.without(HOST, answers)) == ["192.0.2.1"]


def test_addresses_the_host_no_longer_has_change_nothing():
    refusing.leave(_refusal(("192.0.2.9", 443)))
    answers = _answers("192.0.2.1", "192.0.2.2")
    assert _hosts(refusing.without(HOST, answers)) == ["192.0.2.1", "192.0.2.2"]


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(url=URL(f"https://{HOST}/a")),  # not from this session
        SimpleNamespace(came_over=None, came_from=None, url=URL(f"https://{HOST}/a")),
    ],
    ids=["no-attribute", "no-connection"],
)
def test_an_unknown_connection_leaves_nothing_out(response):
    assert refusing.leave(response) is False
    answers = _answers("192.0.2.1")
    assert refusing.without(HOST, answers) is answers
    assert refusing.times_left() == 0


def test_a_connection_without_a_peer_is_closed_and_leaves_nothing_out():
    r = _refusal(peer=None)
    assert refusing.leave(r) is False
    assert r.came_over.closed is True


# ---- the resolver -----------------------------------------------------------


class _Inner(AbstractResolver):
    def __init__(self, hosts, port=443):
        self.hosts, self.port = hosts, port
        self.asked = []
        self.closed = False

    async def resolve(self, host, port=0, family=socket.AF_INET):
        self.asked.append((host, port, family))
        return [
            {
                "hostname": host, "host": h, "port": port or self.port,
                "family": socket.AF_INET, "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
            for h in self.hosts
        ]

    async def close(self):
        self.closed = True


def test_the_resolver_leaves_out_the_address_and_closes_what_it_wraps():
    async def run():
        inner = _Inner(["192.0.2.1", "192.0.2.2"])
        resolver = refusing.Resolver(inner)
        before = await resolver.resolve(HOST, 443, family=socket.AF_INET6)
        refusing.leave(_refusal())
        after = await resolver.resolve(HOST, 443)
        await resolver.close()
        return inner, before, after

    inner, before, after = asyncio.run(run())
    assert _hosts(before) == ["192.0.2.1", "192.0.2.2"]
    assert _hosts(after) == ["192.0.2.2"]
    assert inner.asked[0] == (HOST, 443, socket.AF_INET6)
    assert inner.closed is True


def test_an_async_session_resolves_through_both_resolvers(monkeypatch):
    monkeypatch.setattr(sm.sessionManager, "_get_ssl_context", lambda self: False)

    async def run():
        async with sm.sessionManager() as c:
            # inside the resolver that keeps the addresses (#622)
            resolver = c._session.connector._resolver._inner
            assert isinstance(resolver, refusing.Resolver)
            # Fansly's steering still applies (#683)
            assert isinstance(resolver._inner, address.Resolver)

    asyncio.run(run())


# ---- a real session against two addresses of one host -----------------------


async def _serve(ip, port, handler):
    app = web.Application()
    app.router.add_get("/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, ip, port).start()
    return runner


@pytest.fixture
def unused_port():
    """A port that is free on both loopback addresses."""
    with socket.socket() as first, socket.socket() as second:
        first.bind((REFUSES, 0))
        port = first.getsockname()[1]
        try:
            second.bind((TAKES, port))
        except OSError:
            pytest.skip("this machine has one loopback address only")
        return port


@pytest.fixture
def two_addresses(monkeypatch, unused_port):
    """``run(paths, leave=True)``: the file host at two addresses, the
    first refusing every link. Its requests reuse kept-alive connections
    (#556). ``leave``: do what the
    downloader does when the site still gives a refused link. Returns each
    request's outcome, how many requests each address got, and whether each
    refusal came with a way to leave the address."""
    monkeypatch.setattr(sm.sessionManager, "print_auth_warning", lambda *a: None)

    def run(paths, leave=True, own_session_first=False):
        monkeypatch.setattr(sm.sessionManager, "_get_ssl_context", lambda self: False)
        got = {REFUSES: 0, TAKES: 0}
        offered = []

        async def refuse(request):
            got[REFUSES] += 1
            return web.Response(status=403, text="<Error><Code>AccessDenied</Code></Error>")

        async def take(request):
            got[TAKES] += 1
            return web.Response(text="file")

        async def go():
            runners = [await _serve(REFUSES, unused_port, refuse)]
            outcomes = []
            try:
                runners.append(await _serve(TAKES, unused_port, take))
                inner = _Inner([REFUSES, TAKES], unused_port)
                monkeypatch.setattr(sm.fansly_address, "Resolver", lambda: inner)
                rate = sm.SessionSleep(min_sleep=0)
                # no waiting after a 403 that isn't a signed link's
                forbidden = sm.SessionSleep(
                    sleep=0, min_sleep=0, difmin=0, max_sleep=0,
                    decay_threshold=1000, decay_factor=2, increase_factor=2,
                )
                def session():
                    return sm.sessionManager(
                        retries=1, wait_min=0, wait_max=0, log=QUIET,
                        rate_limit_sleeper=rate, forbidden_sleeper=forbidden,
                    )

                async def get(c, path):
                    try:
                        async with c.requests_async(
                            f"http://{HOST}:{unused_port}{path}",
                            exceptions=[sm.FORBIDDEN],
                        ) as r:
                            outcomes.append(await r.text_())
                    except aiohttp.ClientResponseError as E:
                        outcomes.append(E.status)
                        offered.append(hasattr(E, "leave_address"))
                        return E

                rest = list(paths)
                async with session() as c:
                    if own_session_first:
                        # the first request through a session of its own,
                        # closed before the downloader acts on the refusal;
                        # the other session has the host's addresses saved
                        await get(c, "/saved")
                        async with session() as short_lived:
                            refusal = await get(short_lived, rest.pop(0))
                        if leave and offered[-1]:
                            # over TLS a closed connection tells no address
                            refusal.leave_address.args[0].came_over = _Transport(None)
                            refusal.leave_address()
                    for path in rest:
                        refusal = await get(c, path)
                        if refusal and leave and offered[-1]:
                            refusal.leave_address()
            finally:
                for runner in runners:
                    await runner.cleanup()
            return outcomes

        return asyncio.run(go()), got, offered

    return run


FILES = [f"/files/{n}.jpg?{SIGNING}" for n in range(5)]


def test_after_the_address_is_left_the_other_gets_every_file(two_addresses):
    outcomes, got, offered = two_addresses(FILES)
    # the first file is refused once; the downloader finds the link is still
    # good, leaves the address and asks again
    assert outcomes == [403, "file", "file", "file", "file"]
    assert got == {REFUSES: 1, TAKES: 4}
    assert offered == [True]


def test_a_refusal_through_a_closed_session_frees_the_other_session_too(two_addresses):
    # a protected video's manifest: read through a session of its own, while
    # the download session has the refusing address saved (#623), and a
    # kept-alive connection to it
    outcomes, got, offered = two_addresses(
        ["/files/manifest.mpd?" + SIGNING] + FILES, own_session_first=True
    )
    # "/saved" isn't signed; it went to the first address, the refusing one
    assert outcomes == [403, 403] + ["file"] * 5
    assert got == {REFUSES: 2, TAKES: 5}
    assert offered == [False, True]


@pytest.mark.parametrize(
    "kept, retries, outcome",
    [
        # aiohttp sends a request again once when its connection fails
        (2, 1, "file"),
        # past that, the session's own retries do
        (3, 2, "file"),
        (3, 1, "ServerDisconnectedError"),
    ],
)
def test_kept_connections_to_an_address_left_later_carry_no_request(
    monkeypatch, unused_port, kept, retries, outcome
):
    # the address took links, then began to refuse them: connections to it
    # are waiting in the pool when it is left (#556)
    monkeypatch.setattr(sm.sessionManager, "print_auth_warning", lambda *a: None)
    monkeypatch.setattr(sm.sessionManager, "_get_ssl_context", lambda self: False)
    got = {REFUSES: 0, TAKES: 0}
    refuses_now = []
    together = asyncio.Barrier(kept)

    async def turns_bad(request):
        if not refuses_now:
            # every request of the first round is in before one is answered,
            # so each came over a connection of its own
            await together.wait()
            return web.Response(text="file")
        got[REFUSES] += 1
        return web.Response(status=403, text="<Error><Code>AccessDenied</Code></Error>")

    async def take(request):
        got[TAKES] += 1
        return web.Response(text="file")

    async def go():
        runners = [await _serve(REFUSES, unused_port, turns_bad)]
        try:
            runners.append(await _serve(TAKES, unused_port, take))
            inner = _Inner([REFUSES], unused_port)
            monkeypatch.setattr(sm.fansly_address, "Resolver", lambda: inner)

            async def get(c, n):
                async with c.requests_async(
                    f"http://{HOST}:{unused_port}/files/{n}.jpg?{SIGNING}",
                    exceptions=[sm.FORBIDDEN],
                ) as r:
                    return await r.text_()

            async with sm.sessionManager(
                retries=retries, wait_min=0, wait_max=0, log=QUIET,
                rate_limit_sleeper=sm.SessionSleep(min_sleep=0),
            ) as c:
                assert await asyncio.gather(*(get(c, n) for n in range(kept))) == [
                    "file"
                ] * kept
                inner.hosts = [REFUSES, TAKES]
                refuses_now.append(True)
                with pytest.raises(aiohttp.ClientResponseError) as refusal:
                    await get(c, "refused")
                refusal.value.leave_address()
                try:
                    return await get(c, "next")
                except aiohttp.ServerDisconnectedError as E:
                    return type(E).__name__
        finally:
            for runner in runners:
                await runner.cleanup()

    assert asyncio.run(go()) == outcome
    # the one refusal; nothing went to that address after it was left
    assert got == {REFUSES: 1, TAKES: 1 if outcome == "file" else 0}


# A connection that answered 403 isn't kept (#556), so in the next three the
# request after the refusal goes over a new connection, which the host's
# next address gets. No address is left.


def test_a_refusal_alone_leaves_no_address(two_addresses):
    # the downloader didn't find the link still good (it ran out, #462)
    outcomes, got, offered = two_addresses(FILES[:3], leave=False)
    assert outcomes == [403, "file", "file"]
    assert got == {REFUSES: 1, TAKES: 2}
    assert offered == [True]
    assert refusing.times_left() == 0


def test_a_link_that_is_not_signed_gets_no_way_to_leave(two_addresses):
    outcomes, got, offered = two_addresses(["/files/0.jpg", "/files/1.jpg"])
    assert outcomes == [403, "file"]
    assert got == {REFUSES: 1, TAKES: 1}
    assert offered == [False]
    assert refusing.times_left() == 0


def test_fansly_is_left_to_its_own_handling(two_addresses, monkeypatch):
    monkeypatch.setattr(sm.sites, "is_fansly", lambda: True)
    monkeypatch.setattr(
        sm.fansly_headers, "make_headers", lambda url: {}, raising=False
    )
    outcomes, got, offered = two_addresses(FILES[:2])
    assert outcomes == [403, "file"]
    assert got == {REFUSES: 1, TAKES: 1}
    assert offered == [False]
    assert refusing.times_left() == 0


def _answer(status=403):
    r = _refusal()
    r.status_code = status
    return r


def test_through_a_proxy_there_is_no_way_to_leave():
    # the connection is the proxy's: its address says nothing about the host
    m = sm.sessionManager(log=QUIET, proxy="http://proxy.invalid:8080")
    error = RuntimeError()
    m._offer_to_leave_address(error, _answer())
    assert not hasattr(error, "leave_address")


def test_another_status_gets_no_way_to_leave():
    m = sm.sessionManager(log=QUIET)
    error = RuntimeError()
    m._offer_to_leave_address(error, _answer(status=500))
    assert not hasattr(error, "leave_address")


def test_every_session_looks_hosts_up_again_once_after_an_address_is_left(monkeypatch):
    # the session that got the refusal and any other: each may have saved
    # the address that was left
    got_it, other = sm.sessionManager(log=QUIET), sm.sessionManager(log=QUIET)
    cleared = []
    for name, m in (("got it", got_it), ("other", other)):
        monkeypatch.setattr(m, "clear_dns_cache", lambda name=name: cleared.append(name))
        m._drop_left_addresses()
    assert cleared == []
    first, again = RuntimeError(), RuntimeError()
    got_it._offer_to_leave_address(first, _answer())
    got_it._offer_to_leave_address(again, _answer())
    first.leave_address()
    for m in (got_it, other, got_it, other):
        m._drop_left_addresses()
    assert cleared == ["got it", "other"]
    # the same address again: already left, nothing to look up
    again.leave_address()
    got_it._drop_left_addresses()
    assert cleared == ["got it", "other"]
    # a session made after that starts with nothing saved
    late = sm.sessionManager(log=QUIET)
    monkeypatch.setattr(late, "clear_dns_cache", lambda: cleared.append("late"))
    late._drop_left_addresses()
    assert cleared == ["got it", "other"]
