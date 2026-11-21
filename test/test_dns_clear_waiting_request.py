"""Clearing a session's saved addresses must not fail a waiting request (#622).

aiohttp looks a host up once for every request that needs it at the same
moment: one asks, the rest wait, and each of them reads the saved answer when
it wakes. A clear between the saving and the reading left nothing to read,
and each waiting request failed with a KeyError.

The session's resolver keeps the addresses itself now, and aiohttp's own
keeping is off.
"""

import asyncio
import gc
import socket
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver

import ofscraper.managers.sessionmanager.addresses as addresses
import ofscraper.managers.sessionmanager.refusing as refusing
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.sites.fansly.address as fansly_address

HOST = "files.example.invalid"


def _address(host, port, last=1):
    return {
        "hostname": host, "host": f"127.0.0.{last}", "port": port,
        "family": socket.AF_INET, "proto": 0,
        "flags": socket.AI_NUMERICHOST,
    }


class _Lookup(AbstractResolver):
    """Answers with the local server. ``clears``: how many lookups are
    followed by ``clear`` at the worst moment: after the answer is saved,
    before the requests waiting for it have read it."""

    def __init__(self, clear, clears):
        self.clear, self.clears = clear, clears
        self.lookups = 0

    async def resolve(self, host, port=0, family=socket.AF_INET):
        self.lookups += 1
        # long enough for the other requests to start waiting on this lookup
        await asyncio.sleep(0.05)
        if self.lookups <= self.clears:
            # runs on the loop's next turn, ahead of the waiting requests
            asyncio.get_running_loop().call_soon(self.clear)
        return [_address(host, port)]

    async def close(self):
        pass


def _aiohttp_alone(lookup):
    used = aiohttp.TCPConnector(resolver=lookup)
    return used, used.clear_dns_cache


def _as_the_session(lookup):
    kept = addresses.Resolver(lookup)
    return aiohttp.TCPConnector(resolver=kept, use_dns_cache=False), kept.clear


def _get_at_once(make, clears, requests=4):
    """``requests`` GETs started together through a new connector. Returns
    each one's outcome and the number of lookups made."""

    async def go():
        async def handler(request):
            return web.Response(text="file")

        app = web.Application()
        app.router.add_get("/{tail:.*}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            lookup = _Lookup(lambda: clear(), clears)
            used, clear = make(lookup)
            async with aiohttp.ClientSession(connector=used) as session:

                async def get(n):
                    async with session.get(f"http://{HOST}:{port}/{n}") as r:
                        return await r.text()

                outcomes = await asyncio.gather(
                    *(get(n) for n in range(requests)), return_exceptions=True
                )
        finally:
            await runner.cleanup()
        return outcomes, lookup.lookups

    return asyncio.run(go())


def test_aiohttp_alone_fails_the_waiting_requests():
    # the fault this guards against: if aiohttp stops doing this, its own
    # keeping of addresses could be used again
    outcomes, lookups = _get_at_once(_aiohttp_alone, clears=1)
    assert outcomes[0] == "file"
    assert [type(o) for o in outcomes[1:]] == [KeyError] * 3
    assert lookups == 1


def test_a_clear_while_requests_wait_fails_none():
    outcomes, lookups = _get_at_once(_as_the_session, clears=1)
    assert outcomes == ["file"] * 4
    # the three that waited looked the host up again, once: their addresses
    # are from after the clear
    assert lookups == 2


def test_nothing_changes_without_a_clear():
    outcomes, lookups = _get_at_once(_as_the_session, clears=0)
    assert outcomes == ["file"] * 4
    assert lookups == 1


def test_a_clear_after_every_lookup_still_ends():
    # each lookup serves the request that asked: one fewer waits each time
    outcomes, lookups = _get_at_once(_as_the_session, clears=100)
    assert outcomes == ["file"] * 4
    assert lookups == 4


def test_one_request_waits_on_a_number_of_lookups_and_then_uses_the_last():
    # more requests than lookups one request waits on: the last ones use the
    # answer they were handed, instead of looking the host up for ever
    requests = addresses.LOOKUPS + 2
    outcomes, lookups = _get_at_once(_as_the_session, clears=1000, requests=requests)
    assert outcomes == ["file"] * requests
    assert lookups == addresses.LOOKUPS


# ---- the resolver that keeps the addresses ----------------------------------


class _Inner(AbstractResolver):
    # an asyncio.Event a lookup waits for, when set
    gate = None

    def __init__(self, answers=3, wait=0.0, fails=0):
        self.answers, self.wait, self.fails = answers, wait, fails
        self.asked = []
        self.closed = False

    async def resolve(self, host, port=0, family=socket.AF_INET):
        self.asked.append((host, port, family))
        if self.gate:
            await self.gate.wait()
        if self.wait:
            await asyncio.sleep(self.wait)
        if len(self.asked) <= self.fails:
            raise OSError("no such host")
        return [_address(host, port, last) for last in range(1, self.answers + 1)]

    async def close(self):
        self.closed = True


def _last(answer):
    return [int(a["host"].rsplit(".", 1)[1]) for a in answer]


def _run(coro):
    return asyncio.run(coro)


def test_an_answer_is_kept_and_its_addresses_are_given_in_turn():
    inner = _Inner(answers=3)

    async def go():
        kept = addresses.Resolver(inner)
        return [_last(await kept.resolve(HOST, 443)) for _ in range(4)]

    # as aiohttp's own keeping gives them: each call starts one further on
    assert _run(go()) == [[1, 2, 3], [2, 3, 1], [3, 1, 2], [1, 2, 3]]
    assert len(inner.asked) == 1


def test_requests_at_the_same_moment_share_one_lookup_and_take_turns():
    inner = _Inner(answers=3, wait=0.05)

    async def go():
        kept = addresses.Resolver(inner)
        return await asyncio.gather(*(kept.resolve(HOST, 443) for _ in range(3)))

    assert sorted(_last(a)[0] for a in _run(go())) == [1, 2, 3]
    assert len(inner.asked) == 1


def test_an_answer_is_looked_up_again_after_its_time(monkeypatch):
    inner = _Inner()
    now = [1000.0]
    monkeypatch.setattr(addresses, "time", SimpleNamespace(monotonic=lambda: now[0]))

    async def go():
        kept = addresses.Resolver(inner, kept=10)
        await kept.resolve(HOST, 443)
        now[0] += 10
        await kept.resolve(HOST, 443)
        assert len(inner.asked) == 1
        now[0] += 0.5
        return _last(await kept.resolve(HOST, 443))

    # and the turns start again with the new answer
    assert _run(go()) == [1, 2, 3]
    assert len(inner.asked) == 2


def test_a_waiting_request_gets_the_addresses_from_after_a_clear():
    # the clear comes with a change to which addresses are used (#683, #620)
    class Changing(_Inner):
        async def resolve(self, host, port=0, family=socket.AF_INET):
            self.answers = len(self.asked) + 1
            answer = await super().resolve(host, port, family)
            if len(self.asked) == 1:
                asyncio.get_running_loop().call_soon(kept.clear)
            return answer

    inner = Changing(wait=0.05)
    kept = addresses.Resolver(inner)

    async def go():
        return await asyncio.gather(*(kept.resolve(HOST, 443) for _ in range(3)))

    # one address before the clear, two after
    assert sorted(len(a) for a in _run(go())) == [1, 2, 2]
    assert len(inner.asked) == 2


def test_an_answer_past_its_time_is_still_used_by_those_who_waited_for_it():
    inner = _Inner(wait=0.05)

    async def go():
        kept = addresses.Resolver(inner, kept=-1)
        return await asyncio.gather(*(kept.resolve(HOST, 443) for _ in range(3)))

    assert len(_run(go())) == 3
    assert len(inner.asked) == 1


def test_a_clear_makes_the_next_request_look_the_host_up_again():
    inner = _Inner()

    async def go():
        kept = addresses.Resolver(inner)
        await kept.resolve(HOST, 443)
        kept.clear()
        await kept.resolve(HOST, 443)

    _run(go())
    assert len(inner.asked) == 2


def test_each_host_port_and_family_has_its_own_answer():
    inner = _Inner()

    async def go():
        kept = addresses.Resolver(inner)
        await kept.resolve(HOST, 443)
        await kept.resolve(HOST, 80)
        await kept.resolve("other.example.invalid", 443)
        await kept.resolve(HOST, 443, family=socket.AF_INET6)
        await kept.resolve(HOST, 443)

    _run(go())
    assert inner.asked == [
        (HOST, 443, socket.AF_INET),
        (HOST, 80, socket.AF_INET),
        ("other.example.invalid", 443, socket.AF_INET),
        (HOST, 443, socket.AF_INET6),
    ]


def test_a_lookup_that_fails_raises_to_every_waiting_request_and_is_not_kept():
    inner = _Inner(wait=0.05, fails=1)

    async def go():
        kept = addresses.Resolver(inner)
        first = await asyncio.gather(
            *(kept.resolve(HOST, 443) for _ in range(3)), return_exceptions=True
        )
        return first, _last(await kept.resolve(HOST, 443))

    first, later = _run(go())
    assert [type(o) for o in first] == [OSError] * 3
    assert later == [1, 2, 3]
    assert len(inner.asked) == 2


def test_a_cancelled_request_does_not_take_the_lookup_with_it():
    inner = _Inner()

    async def go():
        inner.gate = asyncio.Event()
        kept = addresses.Resolver(inner)
        first = asyncio.ensure_future(kept.resolve(HOST, 443))
        second = asyncio.ensure_future(kept.resolve(HOST, 443))
        await asyncio.sleep(0.02)
        assert len(inner.asked) == 1
        first.cancel()
        await asyncio.sleep(0)
        inner.gate.set()
        return _last(await second)

    assert len(_run(go())) == 3
    assert len(inner.asked) == 1


def test_a_lookup_that_fails_with_no_request_left_is_not_reported():
    # asyncio logs an error nobody read ("Task exception was never
    # retrieved") when the task is dropped
    inner = _Inner(fails=1)
    reported = []

    async def go():
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, context: reported.append(context)
        )
        inner.gate = asyncio.Event()
        kept = addresses.Resolver(inner)
        only = asyncio.ensure_future(kept.resolve(HOST, 443))
        await asyncio.sleep(0.02)
        only.cancel()
        await asyncio.sleep(0)
        inner.gate.set()
        await asyncio.sleep(0.02)
        # the next request looks the host up again
        assert _last(await kept.resolve(HOST, 443)) == [1, 2, 3]
        del kept
        gc.collect()
        await asyncio.sleep(0)

    _run(go())
    assert len(inner.asked) == 2
    assert reported == []


def test_an_empty_answer_is_handed_on():
    async def go():
        kept = addresses.Resolver(_Inner(answers=0))
        return await kept.resolve(HOST, 443), await kept.resolve(HOST, 443)

    assert _run(go()) == ([], [])


def test_a_lookup_ended_before_it_began_does_not_stay_in_the_way():
    # closed before the lookup's first step: nothing of it runs
    inner = _Inner()

    async def go():
        kept = addresses.Resolver(inner)
        waiting = asyncio.ensure_future(kept.resolve(HOST, 443))
        await asyncio.sleep(0)
        await kept.close()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        return _last(await kept.resolve(HOST, 443))

    assert _run(go()) == [1, 2, 3]


@pytest.mark.skipif(
    not hasattr(asyncio, "eager_task_factory"), reason="Python 3.12 and later"
)
def test_a_lookup_that_ends_as_it_is_started_is_used():
    # with eager tasks, a lookup that never waits is over before the task
    # for it is handed back
    inner = _Inner()

    async def go():
        asyncio.get_running_loop().set_task_factory(asyncio.eager_task_factory)
        kept = addresses.Resolver(inner)
        return [_last(await kept.resolve(HOST, 443)) for _ in range(2)]

    assert _run(go()) == [[1, 2, 3], [2, 3, 1]]
    assert len(inner.asked) == 1


def test_closing_closes_the_inner_resolver_and_ends_a_lookup_under_way():
    inner = _Inner(wait=5)

    async def go():
        kept = addresses.Resolver(inner)
        waiting = asyncio.ensure_future(kept.resolve(HOST, 443))
        await asyncio.sleep(0.02)
        await kept.close()
        with pytest.raises(asyncio.CancelledError):
            await waiting

    _run(go())
    assert inner.closed is True


# ---- the session ------------------------------------------------------------


def test_the_session_keeps_the_addresses_itself(monkeypatch):
    monkeypatch.setattr(sm.sessionManager, "_get_ssl_context", lambda self: False)

    async def go():
        async with sm.sessionManager() as c:
            used = c._session.connector
            # plain aiohttp: nothing of its own is overridden
            assert type(used) is aiohttp.TCPConnector
            assert used.use_dns_cache is False
            kept = used._resolver
            assert isinstance(kept, addresses.Resolver)
            # what is kept is what the other two resolvers decided
            assert isinstance(kept._inner, refusing.Resolver)
            assert isinstance(kept._inner._inner, fansly_address.Resolver)
            kept._answers[("host.invalid", 443, socket.AF_INET)] = [[], 0, 0]
            c.clear_dns_cache()
            assert kept._answers == {}

    asyncio.run(go())


def test_clearing_a_session_that_was_never_opened_does_nothing():
    sm.sessionManager().clear_dns_cache()
