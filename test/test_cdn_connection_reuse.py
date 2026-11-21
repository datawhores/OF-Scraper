"""Requests to the file hosts reuse a kept-alive connection (#556).

aiohttp reuses a connection only for a request whose SSL setting is the
same object as the one that opened it. The session passed a new SSL context
with every request, so every image and every stream segment opened a new
connection. The file hosts (cdn*.fansly.com, cdn*.onlyfans.com) now use the
connector's own context; the API hosts keep a new connection per request.

One local server stands in for every host; the test resolver sends each
name to it. The client's port tells the connections apart. aiohttp keys its
pool on the SSL setting for plain http too, so no certificate is needed.
"""

import asyncio
import logging
import socket
import struct
import threading
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.managers.sessionmanager.cert as cert
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.sites.fansly.address as fansly_address
import ofscraper.utils.settings as settings
from test_tls_clienthello import _fingerprint


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture(params=["default", "custom", "false"])
def ssl_verify(request, monkeypatch):
    site = SimpleNamespace(name="fansly")
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            download_limit=0,
            ssl_verify=request.param,
            cached_disabled=True,
            anon=False,
            site=site.name,
        ),
    )
    request.node.site = site
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


@pytest.mark.parametrize("body", ["with the headers", "after the headers"])
def test_a_connection_that_answered_403_is_not_used_again(request, ssl_verify, body):
    # it would be the next one handed out: the request made after a refusal
    # would go back to the address that refused
    _profile(request, "cdn2.onlyfans.com")
    ports = []

    async def go():
        async def handle(request):
            ports.append(request.transport.get_extra_info("peername")[1])
            if len(ports) != 2:
                return web.Response(body=b"x" * 100)
            if body == "with the headers":
                return web.Response(status=403, text="<Error/>")
            late = web.StreamResponse(status=403)
            await late.prepare(request)
            await asyncio.sleep(0.05)
            await late.write(b"<Error/>")
            return late

        app = web.Application()
        app.router.add_get("/{path}", handle)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        still = sm.SessionSleep(
            sleep=0, min_sleep=0, difmin=0, max_sleep=0,
            decay_threshold=1000, decay_factor=2, increase_factor=2,
        )
        try:
            async with sm.sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test"),
                rate_limit_sleeper=still, forbidden_sleeper=still,
            ) as c:
                statuses = []
                for i in range(5):
                    try:
                        async with c.requests_async(
                            url=f"http://cdn2.onlyfans.com:{port}/f{i}",
                            exceptions=[sm.FORBIDDEN],
                        ) as r:
                            await r.read_()
                            statuses.append(r.status)
                    except aiohttp.ClientResponseError as E:
                        statuses.append(E.status)
                return statuses
        finally:
            await runner.cleanup()

    assert asyncio.run(go()) == [200, 403, 200, 200, 200]
    first, refused, *after = ports
    # the refusal came over the kept connection; the ones after it share
    # another
    assert refused == first
    assert len(set(after)) == 1 and after[0] != refused


def _profile(request, host):
    """A profile of the site ``host`` belongs to."""
    request.node.site.name = "fansly" if "fansly" in host else "onlyfans"


@pytest.mark.parametrize(
    "host", ["cdn3.fansly.com", "cdn2.onlyfans.com", "cdn3.onlyfans.com"]
)
def test_file_host_requests_share_one_connection(request, ssl_verify, host):
    _profile(request, host)
    assert len(set(_client_ports(host))) == 1


@pytest.mark.parametrize("host", ["apiv3.fansly.com", "onlyfans.com"])
def test_api_requests_keep_a_new_connection_each(request, ssl_verify, host):
    _profile(request, host)
    if ssl_verify == "false":
        pytest.skip("False is one value, so aiohttp already reused these")
    assert len(set(_client_ports(host))) == 3


def _client_hello(host):
    """What a TLS fingerprint sees of one https request to host, sent
    through the session. The host name itself (SNI) is left out."""
    out = {}
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)

        def accept():
            conn, _ = listener.accept()
            with conn:
                data = b""
                while len(data) < 5 or len(data) < 5 + struct.unpack(">H", data[3:5])[0]:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
            out["hello"] = data

        async def go():
            async with sm.sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                port = listener.getsockname()[1]
                async with c.requests_async(url=f"https://{host}:{port}/f"):
                    pass

        thread = threading.Thread(target=accept)
        thread.start()
        # the listener hangs up after the ClientHello
        with pytest.raises(Exception):  # noqa: B017, PT011
            asyncio.run(go())
        thread.join(timeout=15)
    seen = _fingerprint(out["hello"])
    names = seen["extensions"].pop(0)
    assert host.encode() in names
    del seen["length"]
    return seen


@pytest.mark.parametrize(
    "file_host, api_host",
    [("cdn2.onlyfans.com", "onlyfans.com"), ("cdn3.fansly.com", "apiv3.fansly.com")],
)
def test_a_file_host_request_sends_the_client_hello_of_an_api_request(
    request, ssl_verify, file_host, api_host
):
    # AGENTS.md rule 5. A file host's requests use the connector's SSL
    # context, an API host's get a new one each: the same setting made both
    _profile(request, file_host)
    kept = _client_hello(file_host)
    assert kept == _client_hello(api_host)
    if ssl_verify == "custom":
        assert kept["session_id_len"] == 0


@pytest.mark.parametrize(
    "url, reuses",
    [
        ("https://cdn3.fansly.com/a.jpg?Policy=x", True),
        ("https://cdn.fansly.com/a", True),
        ("https://apiv3.fansly.com/api/v1/account", False),
        ("https://fansly.com/", False),
        ("https://cdn3.fansly.com.example.org/a", False),
        ("https://cdn3.notfansly.com/a", False),
        ("https://cdn3.onlyfans.com/files/a.jpg?Policy=x", True),
        ("https://cdn2.onlyfans.com/a", True),
        ("https://onlyfans.com/api2/v2/users/me", False),
        ("https://public.onlyfans.com/a", False),
        ("https://cdn3.onlyfans.com.example.org/a", False),
        ("https://cdn3.notonlyfans.com/a", False),
        ("not a link", False),
        (None, False),
    ],
)
def test_which_hosts_reuse_connections(url, reuses):
    assert sm._reuses_connections(url) is reuses
