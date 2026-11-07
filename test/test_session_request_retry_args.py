"""retries, wait_min, wait_max (and log, on the sync path) passed to a
request must win over the session's defaults.

Both request methods read them with kwargs.get(...), but they're named
parameters, so they never land in kwargs and the passed value was ignored
(#154).
"""

import asyncio
import threading
import time
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


class Log:
    def __init__(self):
        self.lines = []

    def debug(self, msg, *a, **k):
        self.lines.append(msg)

    def traceback_(self, *a, **k):
        pass


def session(log=None):
    # session defaults: 5 tries, no wait
    return sessionManager(retries=5, wait_min=0, wait_max=0, log=log or Log())


class FailingServer:
    """Answers every request with a 500, on its own thread and loop."""

    def __init__(self):
        self.calls = 0
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.ready.wait(5)

    async def _handler(self, request):
        self.calls += 1
        return web.Response(status=500, text="try again")

    def _run(self):
        asyncio.set_event_loop(self.loop)
        app = web.Application()
        app.router.add_get("/f", self._handler)
        self.runner = web.AppRunner(app)
        self.loop.run_until_complete(self.runner.setup())
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        self.loop.run_until_complete(site.start())
        self.url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/f"
        self.ready.set()
        self.loop.run_forever()

    def close(self):
        asyncio.run_coroutine_threadsafe(self.runner.cleanup(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.loop.close()


@pytest.fixture
def server():
    s = FailingServer()
    yield s
    s.close()


def fetch_async(url, **kw):
    async def go():
        async with session() as c:
            async with c.requests_async(url=url, **kw):
                pass

    start = time.monotonic()
    with pytest.raises(Exception):
        asyncio.run(go())
    return time.monotonic() - start


def fetch_sync(url, log=None, **kw):
    start = time.monotonic()
    with pytest.raises(Exception):
        with session(log) as c:
            with c.requests(url, **kw):
                pass
    # the session pauses 1 s on close
    return time.monotonic() - start - 1


def test_async_request_uses_the_retries_passed_in(server):
    fetch_async(server.url, retries=2)
    assert server.calls == 2


def test_async_request_uses_the_waits_passed_in(server):
    seconds = fetch_async(server.url, retries=2, wait_min=0.6, wait_max=0.6)
    assert server.calls == 2
    assert seconds >= 0.5


def test_sync_request_uses_the_retries_passed_in(server):
    fetch_sync(server.url, retries=2)
    assert server.calls == 2


def test_sync_request_uses_the_waits_passed_in(server):
    seconds = fetch_sync(server.url, retries=2, wait_min=0.6, wait_max=0.6)
    assert server.calls == 2
    assert seconds >= 0.5


def test_sync_request_logs_to_the_log_passed_in(server):
    session_log, request_log = Log(), Log()
    with pytest.raises(Exception):
        with session(session_log) as c:
            with c.requests(server.url, retries=2, log=request_log):
                pass
    assert any("attempt: 2" in line for line in request_log.lines)
    assert not any("attempt: 2" in line for line in session_log.lines)


def test_zero_wait_passed_in_is_kept(server):
    # 0 is a real value, not "use the default"
    async def go():
        async with sessionManager(retries=5, wait_min=1, wait_max=1, log=Log()) as c:
            async with c.requests_async(
                url=server.url, retries=3, wait_min=0, wait_max=0
            ):
                pass

    start = time.monotonic()
    with pytest.raises(Exception):
        asyncio.run(go())
    assert server.calls == 3
    assert time.monotonic() - start < 1.5
