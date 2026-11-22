"""A kept connection that takes a request and never answers is given up on
soon, not after the whole read timeout (#636).

When a kept connection's network path dies without the connection being
closed (a VPN reconnects), the next request over it gets nothing back. It
waited for the read timeout (30 seconds for downloads) before it was retried.
On a connection used before, a GET's answer must now start within a third
of the read timeout; after that, the read timeout applies as before.

A server that holds the second request without answering stands in for the
dead path. Fixtures and helpers come from test_cdn_connection_reuse.
"""

import asyncio
import logging
import time

import pytest
from aiohttp import web

import ofscraper.managers.sessionmanager.sessionmanager as sm
from test_cdn_connection_reuse import _profile, ssl_verify  # noqa: F401

HOST = "cdn2.onlyfans.com"
BODY = b"x" * 100
# a third of it, 1 s, is the cap on a kept connection
READ_TIMEOUT = 3

# each ssl_verify mode, a host resolved to the local server, no auth read
pytestmark = pytest.mark.usefixtures("ssl_verify")


def _fetch(handle, methods, read_timeout=READ_TIMEOUT):
    """Send a request with each of methods to HOST, one after another. The
    client port of each request the server got, the bodies read, and the
    seconds it took."""
    ports = []

    async def go():
        held = asyncio.Event()

        async def handler(request):
            ports.append(request.transport.get_extra_info("peername")[1])
            return await handle(request, len(ports), held)

        app = web.Application()
        app.router.add_route("*", "/{path}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        bodies = []
        start = time.monotonic()
        try:
            async with sm.sessionManager(
                retries=2, wait_min=0, wait_max=0, read_timeout=read_timeout,
                log=logging.getLogger("test"),
            ) as c:
                for i, method in enumerate(methods):
                    async with c.requests_async(
                        url=f"http://{HOST}:{port}/f{i}", method=method
                    ) as r:
                        bodies.append(await r.read_())
        finally:
            seconds = time.monotonic() - start
            held.set()
            await runner.cleanup()
        return bodies, seconds

    # a hang fails here rather than after a long read timeout
    bodies, seconds = asyncio.run(asyncio.wait_for(go(), 15))
    return ports, bodies, seconds


async def _answer_late(seconds):
    await asyncio.sleep(seconds)
    return web.Response(body=BODY)


def test_a_kept_connection_that_never_answers_is_retried_soon(request):
    _profile(request, HOST)

    async def handle(request, n, held):
        if n == 2:
            # the request arrived over the kept connection; no answer comes
            await held.wait()
        return web.Response(body=BODY)

    ports, bodies, seconds = _fetch(handle, ["get", "get"])
    assert bodies == [BODY, BODY]
    first, unanswered, retried = ports
    assert unanswered == first
    # the silent connection was closed; the retry went over a new one
    assert retried != first
    # the cap is 1 s; without it, the read timeout is 3 s
    assert seconds < 2.5


def test_a_slow_body_on_a_kept_connection_is_still_waited_for(request):
    _profile(request, HOST)

    async def handle(request, n, held):
        if n == 1:
            return web.Response(body=BODY)
        slow = web.StreamResponse()
        slow.content_length = len(BODY)
        await slow.prepare(request)
        # longer than the cap, shorter than the read timeout
        await asyncio.sleep(2)
        await slow.write(BODY)
        return slow

    ports, bodies, _ = _fetch(handle, ["get", "get"])
    assert bodies == [BODY, BODY]
    # one connection, no retry
    assert len(ports) == 2 and ports[0] == ports[1]


def test_no_cap_when_the_read_timeout_is_no_limit(request):
    _profile(request, HOST)

    async def handle(request, n, held):
        return await _answer_late(0.5 if n == 2 else 0)

    ports, bodies, _ = _fetch(handle, ["get", "get"], read_timeout=0)
    assert bodies == [BODY, BODY]
    assert len(ports) == 2 and ports[0] == ports[1]


def test_a_post_on_a_kept_connection_is_not_capped(request):
    # a POST may not be safe to send twice (a licence request)
    _profile(request, HOST)

    async def handle(request, n, held):
        # longer than the cap, shorter than the read timeout
        return await _answer_late(2 if n == 2 else 0)

    ports, bodies, _ = _fetch(handle, ["get", "post"])
    assert bodies == [BODY, BODY]
    # sent once, over the kept connection
    assert len(ports) == 2 and ports[0] == ports[1]
