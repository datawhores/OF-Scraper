"""Requests to Fansly's CDN reuse a kept-alive connection (#556).

aiohttp reuses a connection only for a request whose SSL setting is the
same object as the one that opened it. The session passed a new SSL context
with every request, so every image and every stream segment opened a new
connection. Fansly's CDN hosts now use the connector's own context; its API
host and OnlyFans keep a new connection per request.

One local server stands in for every host; the test resolver sends each
name to it. The client's port tells the connections apart. aiohttp keys its
pool on the SSL setting for plain http too, so no certificate is needed.
"""

import asyncio
import logging
import socket
from types import SimpleNamespace

import pytest
from aiohttp import web

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.managers.sessionmanager.cert as cert
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.sites.fansly.address as fansly_address
import ofscraper.utils.settings as settings


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture(params=["default", "custom", "false"])
def ssl_verify(request, monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            download_limit=0,
            ssl_verify=request.param,
            cached_disabled=True,
            anon=False,
            site="fansly",
        ),
    )
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)
    # the custom context's seed, without reading anyone's auth
    monkeypatch.setattr(cert, "_fansly_seed", lambda: "fansly_test_seed")

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
    return request.param


def _client_ports(host, count=3):
    """The client port of each of count requests to host, sent one after
    another, each read to the end."""
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
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                for i in range(count):
                    async with c.requests_async(url=f"http://{host}:{port}/f{i}") as r:
                        assert await r.read_() == b"x" * 100
        finally:
            await runner.cleanup()

    asyncio.run(go())
    assert len(ports) == count
    return ports


def test_fansly_cdn_requests_share_one_connection(ssl_verify):
    assert len(set(_client_ports("cdn3.fansly.com"))) == 1


@pytest.mark.parametrize("host", ["apiv3.fansly.com", "cdn3.onlyfans.com", "onlyfans.com"])
def test_api_and_onlyfans_requests_keep_a_new_connection_each(ssl_verify, host):
    if ssl_verify == "false":
        pytest.skip("False is one value, so aiohttp already reused these")
    assert len(set(_client_ports(host))) == 3


@pytest.mark.parametrize(
    "url, reuses",
    [
        ("https://cdn3.fansly.com/a.jpg?Policy=x", True),
        ("https://cdn.fansly.com/a", True),
        ("https://apiv3.fansly.com/api/v1/account", False),
        ("https://fansly.com/", False),
        ("https://cdn3.fansly.com.example.org/a", False),
        ("https://cdn3.notfansly.com/a", False),
        ("https://cdn3.onlyfans.com/a", False),
        ("not a link", False),
        (None, False),
    ],
)
def test_which_hosts_reuse_connections(url, reuses):
    assert sm._reuses_connections(url) is reuses
