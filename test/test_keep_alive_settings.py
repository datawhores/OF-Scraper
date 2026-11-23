"""KEEP_ALIVE_EXP sets how long an idle connection is kept, for both clients (#627).

It reached the sync client (httpx) only. The async client (aiohttp), which
downloads, kept idle connections for its own 15 seconds whatever the setting
said. KEEP_ALIVE is a count of idle connections, and only the sync client has
one.

One local server stands in for the host; the test resolver sends the name to
it. The client's port tells the connections apart. With ssl_verify "false"
every request has the same SSL setting, so aiohttp uses a kept connection
again.
"""

import asyncio
import logging
import socket
from types import SimpleNamespace

import pytest

from aiohttp import web

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.sites.fansly.address as fansly_address
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture(autouse=True)
def _one_ssl_setting(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            download_limit=0,
            ssl_verify="false",
            cached_disabled=True,
            anon=False,
            site="onlyfans",
        ),
    )
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)

    async def resolve(self, host, port=0, family=socket.AF_INET):
        return [
            {
                "hostname": host,
                "host": "127.0.0.1",
                "port": port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
        ]

    monkeypatch.setattr(fansly_address.Resolver, "resolve", resolve)


def _connections(idle, **session):
    """How many connections two requests used, the second sent ``idle``
    seconds after the first was read to the end."""
    ports = []

    async def go():
        async def handle(request):
            ports.append(request.transport.get_extra_info("peername")[1])
            return web.Response(body=b"x" * 100)

        app = web.Application()
        app.router.add_get("/{path}", handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with sm.sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test"), **session
            ) as c:
                for i in range(2):
                    if i:
                        await asyncio.sleep(idle)
                    async with c.requests_async(url=f"http://files.example:{port}/f{i}") as r:
                        assert await r.read_() == b"x" * 100
        finally:
            await runner.cleanup()

    asyncio.run(go())
    assert len(ports) == 2
    return len(set(ports))


def test_an_idle_connection_is_kept_for_the_time_given():
    assert _connections(idle=1.5, keep_alive_exp=30) == 1


def test_an_idle_connection_is_not_kept_past_the_time_given():
    # aiohttp's own 15 seconds would have kept it
    assert _connections(idle=1.5, keep_alive_exp=1) == 2


def _setting(monkeypatch, **values):
    real = of_env.getattr
    monkeypatch.setattr(
        of_env, "getattr", lambda key, *a, **k: values[key] if key in values else real(key, *a, **k)
    )


def test_the_time_comes_from_the_setting_when_none_is_given(monkeypatch):
    _setting(monkeypatch, KEEP_ALIVE_EXP=1)
    assert _connections(idle=1.5) == 2


def test_both_clients_get_the_setting(monkeypatch):
    _setting(monkeypatch, KEEP_ALIVE_EXP=7, KEEP_ALIVE=3)

    async def the_async_one():
        async with sm.sessionManager(log=logging.getLogger("test")) as c:
            return c._session.connector._keepalive_timeout

    assert asyncio.run(the_async_one()) == 7
    with sm.sessionManager(log=logging.getLogger("test")) as c:
        pool = c._session._transport._pool
        assert pool._keepalive_expiry == 7
        # the count of idle connections is the sync client's alone
        assert pool._max_keepalive_connections == 3


def test_the_default_is_ten_seconds():
    # whatever the machine that runs the tests has set
    with of_env.builtin_defaults():
        assert of_env.getattr("KEEP_ALIVE_EXP") == 10


@pytest.mark.slow
@pytest.mark.parametrize("seconds", [0, -5])
def test_kept_for_no_time_means_closed_after_use(seconds):
    """Given 0, aiohttp never closed an idle connection: it only cleans up
    for a time above 0 (#637)."""
    transports = []

    async def go():
        async def handle(request):
            transports.append(request.transport)
            return web.Response(body=b"x" * 100)

        app = web.Application()
        app.router.add_get("/{path}", handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            async with sm.sessionManager(
                retries=1,
                wait_min=0,
                wait_max=0,
                log=logging.getLogger("test"),
                keep_alive_exp=seconds,
            ) as c:
                for i in range(3):
                    async with c.requests_async(
                        url=f"http://files.example:{port}/f{i}"
                    ) as r:
                        assert await r.read_() == b"x" * 100
                # time for the server to see each connection closed
                await asyncio.sleep(0.5)
                return [t.is_closing() for t in transports]
        finally:
            await runner.cleanup()

    # while the session is still open: none is left open and idle
    assert asyncio.run(go()) == [True, True, True]
