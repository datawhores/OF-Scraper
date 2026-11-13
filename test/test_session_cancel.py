"""Cancelling requests_async must stop the request, not retry it.

The retry loop only skipped KeyboardInterrupt and SystemExit, so tenacity's
attempt swallowed asyncio.CancelledError and sent the request again (#155).
A cancel while an error response's body is read for the log must also end
with that response closed (aiohttp's read() closes it).
"""

import asyncio
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


QUIET = SimpleNamespace(traceback_=lambda *a, **k: None, debug=lambda *a, **k: None)


async def serve(handler):
    app = web.Application()
    app.router.add_get("/f", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}/f"


async def cancel_after(c, url, delay=0.3, wait=3):
    """Start a request, cancel it, and report whether the cancel stopped it."""

    async def request():
        async with c.requests_async(url=url):
            pass

    task = asyncio.create_task(request())
    await asyncio.sleep(delay)
    task.cancel()
    done, _ = await asyncio.wait({task}, timeout=wait)
    stopped = task in done and task.cancelled()
    # clean up a request that kept going
    while not task.done():
        task.cancel()
        await asyncio.wait({task}, timeout=1)
    return stopped


def test_cancel_while_waiting_for_headers_stops_the_request():
    calls = []
    release = asyncio.Event()

    async def silent(request):
        calls.append(1)
        await release.wait()
        return web.Response(text="late")

    async def run():
        runner, url = await serve(silent)
        try:
            async with sessionManager(
                sem_count=1, retries=3, wait_min=0, wait_max=0, log=QUIET
            ) as c:
                stopped = await cancel_after(c, url)
                attempts = len(calls)
                free = c._sem._value
        finally:
            release.set()
            await runner.cleanup()
        return stopped, attempts, free

    stopped, attempts, free = asyncio.run(run())
    assert stopped, f"the cancel was swallowed; {attempts} requests were sent"
    assert attempts == 1
    assert free == 1


def test_cancel_while_reading_an_error_body_closes_the_response():
    calls = []
    transports = []
    release = asyncio.Event()

    async def stalled_error(request):
        calls.append(1)
        transports.append(request.transport)
        resp = web.StreamResponse(status=500, headers={"Content-Length": "100000"})
        await resp.prepare(request)
        await resp.write(b"e" * 100)
        await release.wait()
        return resp

    async def run():
        runner, url = await serve(stalled_error)
        try:
            async with sessionManager(
                sem_count=1, retries=3, wait_min=0, wait_max=0, log=QUIET
            ) as c:
                stopped = await cancel_after(c, url)
                attempts = len(calls)
                in_use = len(c._session.connector._acquired)
                await asyncio.sleep(0.2)
                open_ = sum(1 for t in transports if t and not t.is_closing())
                free = c._sem._value
        finally:
            release.set()
            await runner.cleanup()
        return stopped, attempts, in_use, open_, free

    stopped, attempts, in_use, open_, free = asyncio.run(run())
    assert stopped, f"the cancel was swallowed; {attempts} requests were sent"
    assert attempts == 1
    assert in_use == 0
    assert open_ == 0
    assert free == 1


def test_timeout_around_a_request_ends_it():
    calls = []
    release = asyncio.Event()

    async def silent(request):
        calls.append(1)
        await release.wait()
        return web.Response(text="late")

    async def run():
        runner, url = await serve(silent)
        try:
            async with sessionManager(
                retries=3, wait_min=0, wait_max=0, log=QUIET
            ) as c:

                async def request():
                    async with c.requests_async(url=url):
                        pass

                outer = asyncio.create_task(asyncio.wait_for(request(), 0.3))
                done, _ = await asyncio.wait({outer}, timeout=3)
                result = outer.exception() if outer in done else "still running"
                while not outer.done():
                    outer.cancel()
                    await asyncio.wait({outer}, timeout=1)
        finally:
            release.set()
            await runner.cleanup()
        return result, len(calls)

    result, attempts = asyncio.run(run())
    assert isinstance(result, asyncio.TimeoutError), f"{result}; {attempts} requests"
    assert attempts == 1
