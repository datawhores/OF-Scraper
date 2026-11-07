"""The download speed limit (--download-limit) must slow downloads down.

download_session and metadata_session applied the limit in an override of
_httpx_funct_async, a method nothing calls: requests_async goes through
_aio_funct. So the limit had no effect (#153).
"""

import asyncio
import time
from types import SimpleNamespace

import pytest
from aiohttp import web

import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.ofsession import (
    download_session,
    metadata_session,
)

LIMIT = 256 * 1024  # bytes per second
BODY = b"x" * (3 * LIMIT)
QUIET = SimpleNamespace(
    traceback_=lambda *a, **k: None,
    debug=lambda *a, **k: None,
    warning=lambda *a, **k: None,
)


def use_limit(monkeypatch, limit):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            ssl_verify="false",
            cached_disabled=True,
            download_limit=limit,
            command="download",
        ),
    )


async def serve():
    async def body(request):
        return web.Response(body=BODY)

    app = web.Application()
    app.router.add_get("/f", body)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}/f"


def download(session_class, chunk_size):
    async def run():
        runner, url = await serve()
        try:
            async with session_class(log=QUIET, wait_min=0, wait_max=0) as c:
                # no auth for a local server
                c._create_headers = lambda headers, *a: headers or {}
                c._create_cookies = lambda: None
                start = time.monotonic()
                received = 0
                async with c.requests_async(url=url) as r:
                    async for chunk in r.iter_chunked(chunk_size):
                        received += len(chunk)
                seconds = time.monotonic() - start
        finally:
            await runner.cleanup()
        return received, seconds

    return asyncio.run(run())


def test_download_session_keeps_to_the_limit(monkeypatch):
    use_limit(monkeypatch, LIMIT)
    received, seconds = download(download_session, 64 * 1024)
    assert received == len(BODY)
    # 3 s of data; the first second's worth may arrive at once
    assert 1.6 < seconds < 4, seconds


def test_metadata_session_keeps_to_the_limit_once(monkeypatch):
    # metadata reads in 30 MB chunks, more than the limit allows per second;
    # it inherits download_session's limit and mustn't apply it twice
    use_limit(monkeypatch, LIMIT)
    received, seconds = download(metadata_session, 30 * 1024 * 1024)
    assert received == len(BODY)
    assert 1.6 < seconds < 4, seconds


def test_no_limit_is_not_slowed(monkeypatch):
    use_limit(monkeypatch, 0)
    received, seconds = download(download_session, 64 * 1024)
    assert received == len(BODY)
    assert seconds < 1, seconds
