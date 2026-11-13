"""requests_async must close a streamed response when the caller's code fails.

Before the fix, an error raised while the caller was reading the response
(e.g. a read timeout on a stalled CDN download) was thrown back into the
retry loop. tenacity swallowed it, sent a new request and yielded again, so
the caller got "async generator ignored GeneratorExit" and every failed
download left its connections open with unread data (datawhores/OF-Scraper#655).
"""

import asyncio
import gc
from types import SimpleNamespace

import pytest
from aiohttp import web

import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager


@pytest.fixture(autouse=True)
def plain_settings(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(ssl_verify="false", cached_disabled=True),
    )


async def serve(handler):
    app = web.Application()
    app.router.add_get("/f", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}/f"


def session():
    return sessionManager(
        sem_count=2, retries=3, wait_min=0, wait_max=0, read_timeout=0.5
    )


def connected(transports):
    return sum(1 for t in transports if t is not None and not t.is_closing())


def test_stalled_stream_is_closed_and_not_requested_again():
    transports = []
    stop = asyncio.Event()

    async def stalled(request):
        transports.append(request.transport)
        resp = web.StreamResponse(headers={"Content-Length": str(10 * 1024 * 1024)})
        await resp.prepare(request)
        await resp.write(b"x" * 65536)
        await stop.wait()
        return resp

    async def run():
        runner, url = await serve(stalled)
        errors = []
        try:
            async with session() as c:
                for _ in range(3):
                    try:
                        async with c.requests_async(url=url, total_timeout=None) as r:
                            async for _ in r.iter_chunked(65536):
                                pass
                    except Exception as E:
                        errors.append(E)
                    gc.collect()
                    await asyncio.sleep(0.2)
                in_use = len(c._session.connector._acquired)
                still_connected = connected(transports)
        finally:
            stop.set()
            await runner.cleanup()
        return errors, in_use, still_connected

    errors, in_use, still_connected = asyncio.run(run())
    # the caller sees the real timeout, once per download, and no retry inside
    assert len(errors) == 3
    assert all(isinstance(E, asyncio.TimeoutError) for E in errors), errors
    assert len(transports) == 3
    # and nothing is left open
    assert in_use == 0
    assert still_connected == 0


def test_completed_stream_is_released():
    async def ok(request):
        return web.Response(body=b"y" * 200000)

    async def run():
        runner, url = await serve(ok)
        try:
            async with session() as c:
                async with c.requests_async(url=url) as r:
                    body = b"".join([x async for x in r.iter_chunked(65536)])
                in_use = len(c._session.connector._acquired)
        finally:
            await runner.cleanup()
        return body, in_use

    body, in_use = asyncio.run(run())
    assert body == b"y" * 200000
    assert in_use == 0


def test_failed_status_is_still_retried():
    calls = []

    async def flaky(request):
        calls.append(1)
        if len(calls) < 3:
            return web.Response(status=500, text="try again")
        return web.Response(text="done")

    async def run():
        runner, url = await serve(flaky)
        try:
            async with session() as c:
                async with c.requests_async(url=url) as r:
                    text = await r.text_()
                in_use = len(c._session.connector._acquired)
        finally:
            await runner.cleanup()
        return text, in_use

    text, in_use = asyncio.run(run())
    assert text == "done"
    assert len(calls) == 3
    assert in_use == 0
