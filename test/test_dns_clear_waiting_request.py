"""Clearing a session's saved addresses must not fail a waiting request (#622).

aiohttp looks a host up once for every request that needs it at the same
moment: one asks, the rest wait, and each of them reads the saved answer when
it wakes. A clear between the saving and the reading left nothing to read,
and each waiting request failed with a KeyError.
"""

import asyncio
import socket
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver

import ofscraper.managers.sessionmanager.connector as connector
import ofscraper.managers.sessionmanager.sessionmanager as sm

HOST = "files.example.invalid"
QUIET = SimpleNamespace(debug=lambda *a: None, traceback_=lambda *a: None)


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
        return [
            {
                "hostname": host, "host": "127.0.0.1", "port": port,
                "family": socket.AF_INET, "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
        ]

    async def close(self):
        pass


def _get_at_once(make_connector, clears, requests=4):
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
            lookup = _Lookup(lambda: used.clear_dns_cache(), clears)
            used = make_connector(resolver=lookup)
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
    # the fault this guards against: if aiohttp stops doing this, the
    # connector below is no longer needed
    outcomes, lookups = _get_at_once(aiohttp.TCPConnector, clears=1)
    assert outcomes[0] == "file"
    assert [type(o) for o in outcomes[1:]] == [KeyError] * 3
    assert lookups == 1


def test_a_clear_while_requests_wait_fails_none():
    outcomes, lookups = _get_at_once(connector.Connector, clears=1)
    assert outcomes == ["file"] * 4
    # the three that found nothing saved looked the host up again, once
    assert lookups == 2


def test_nothing_changes_without_a_clear():
    outcomes, lookups = _get_at_once(connector.Connector, clears=0)
    assert outcomes == ["file"] * 4
    assert lookups == 1


def test_a_clear_after_every_lookup_still_ends():
    # each lookup serves the request that made it: one fewer waits each time
    outcomes, lookups = _get_at_once(connector.Connector, clears=100)
    assert outcomes == ["file"] * 4
    assert lookups == 4


def test_one_request_gives_up_after_a_number_of_lookups():
    # more requests than lookups one request makes: the last ones raise what
    # aiohttp raised, instead of looking the host up for ever
    requests = connector.LOOKUPS + 2
    outcomes, lookups = _get_at_once(
        connector.Connector, clears=1000, requests=requests
    )
    got = outcomes.count("file")
    # which request makes a lookup first differs by Python version
    assert got in (connector.LOOKUPS - 1, connector.LOOKUPS)
    assert [type(o) for o in outcomes if o != "file"] == [KeyError] * (requests - got)
    assert lookups == got


def test_a_lookup_that_fails_is_not_made_again():
    class Fails(AbstractResolver):
        lookups = 0

        async def resolve(self, host, port=0, family=socket.AF_INET):
            Fails.lookups += 1
            raise OSError("no such host")

        async def close(self):
            pass

    async def go():
        used = connector.Connector(resolver=Fails())
        async with aiohttp.ClientSession(connector=used) as session:
            with pytest.raises(aiohttp.ClientConnectorError):
                await session.get(f"http://{HOST}:1/")

    asyncio.run(go())
    assert Fails.lookups == 1


def test_a_keyerror_of_the_lookup_itself_is_raised_at_once():
    class Broken(AbstractResolver):
        lookups = 0

        async def resolve(self, host, port=0, family=socket.AF_INET):
            Broken.lookups += 1
            raise KeyError("broken resolver")

        async def close(self):
            pass

    async def go():
        used = connector.Connector(resolver=Broken())
        async with aiohttp.ClientSession(connector=used) as session:
            with pytest.raises(KeyError, match="broken resolver"):
                await session.get(f"http://{HOST}:1/")

    asyncio.run(go())
    assert Broken.lookups == 1


def test_the_session_uses_the_connector(monkeypatch):
    monkeypatch.setattr(sm.sessionManager, "_get_ssl_context", lambda self: False)

    async def go():
        async with sm.sessionManager(log=QUIET) as c:
            assert isinstance(c._session.connector, connector.Connector)

    asyncio.run(go())
