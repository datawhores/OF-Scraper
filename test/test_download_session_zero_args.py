"""A 0 passed to the download session must be kept, not replaced.

download_session set its defaults with `x or default`, so 0 retries or a
0 s wait passed to it became the default (#174, item 1). Only None means
"use the default".
"""

import asyncio
import socket
import threading
import time
from types import SimpleNamespace

import pytest
from aiohttp import web

import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.ofsession import download_session

QUIET = SimpleNamespace(
    traceback_=lambda *a, **k: None,
    debug=lambda *a, **k: None,
    warning=lambda *a, **k: None,
)


@pytest.fixture(autouse=True)
def plain_settings(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            ssl_verify="false",
            cached_disabled=True,
            download_limit=0,
            command="download",
        ),
    )


def failing_requests(**session_args):
    """Count requests to a server that always answers 500, and time them."""
    calls = []

    async def fail(request):
        calls.append(1)
        return web.Response(status=500, text="try again")

    async def run():
        app = web.Application()
        app.router.add_get("/f", fail)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/f"
        try:
            async with download_session(log=QUIET, **session_args) as c:
                # no auth for a local server
                c._create_headers = lambda headers, *a: headers or {}
                c._create_cookies = lambda: None
                start = time.monotonic()
                with pytest.raises(Exception):
                    async with c.requests_async(url=url):
                        pass
                return len(calls), time.monotonic() - start
        finally:
            await runner.cleanup()

    return asyncio.run(run())


def test_zero_waits_are_kept():
    calls, seconds = failing_requests(retries=3, wait_min=0, wait_max=0)
    assert calls == 3
    # the default waits are 2 to 3 s between tries
    assert seconds < 1, seconds


def test_zero_retries_is_kept():
    # stop_after_attempt(0) stops after the first try
    calls, _ = failing_requests(retries=0, wait_min=0, wait_max=0)
    assert calls == 1


def slow_server():
    """Answers each request after 1.5 s, on its own thread."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)

    def reply(conn):
        with conn:
            conn.recv(65536)
            time.sleep(1.5)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
            )

    def accept():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            threading.Thread(target=reply, args=(conn,), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    return sock, f"http://127.0.0.1:{sock.getsockname()[1]}/f"


def test_zero_read_timeout_means_no_limit():
    # 0 means no limit, as for OFSC_READ_TIMEOUT (#167): aiohttp reads 0 that
    # way, but httpx reads 0 as "fail at once"
    assert download_session(log=QUIET, read_timeout=0)._read_timeout is None


def test_zero_read_timeout_means_no_limit_on_the_sync_path():
    sock, url = slow_server()
    try:
        with download_session(log=QUIET, read_timeout=0, retries=1) as c:
            with c.requests(url) as r:
                assert r.text_() == "ok"
    finally:
        sock.close()


def test_zero_read_timeout_means_no_limit_on_the_async_path():
    sock, url = slow_server()

    async def go():
        async with download_session(log=QUIET, read_timeout=0, retries=1) as c:
            c._create_headers = lambda headers, *a: headers or {}
            c._create_cookies = lambda: None
            async with c.requests_async(url=url) as r:
                return await r.text_()

    try:
        assert asyncio.run(go()) == "ok"
    finally:
        sock.close()


def test_none_still_means_the_default():
    c = download_session(log=QUIET)
    assert c._retries > 0
    assert c._wait_min > 0
    assert c._read_timeout > 0
