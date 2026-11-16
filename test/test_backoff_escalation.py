"""A rate limit that outlasts the first wait makes the wait grow.

The wait rose only when 30 s had passed since its last change, and an API
request made its 3 tries in about 15 s: it failed with a 429 while the wait
was still at its starting value. A decay also counted as a change, so a 429
in the 30 s after one changed nothing, and the wait decayed while 429s were
still coming in.
"""

import asyncio
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web

import ofscraper.managers.sessionmanager.sessionmanager as sm


def sleeper(min_sleep=0.5, sleep=2.5):
    # the API session defaults
    return sm.SessionSleep(
        sleep=sleep,
        min_sleep=min_sleep,
        difmin=30,
        max_sleep=180,
        decay_threshold=120,
        decay_factor=1.5,
        increase_factor=2,
        error_name="test",
    )


def ago(seconds):
    return sm.arrow.now().shift(seconds=-seconds)


def test_a_request_sent_after_the_raise_raises_the_wait_at_once():
    s = sleeper()
    s.toomany_req()
    s._last_raise = ago(5)
    # sent 2 s ago, after the raise 5 s ago, and still refused
    s.toomany_req(sent_at=ago(2))
    assert s.sleep == 5


def test_requests_sent_before_the_raise_are_one_burst():
    s = sleeper()
    sent = ago(5)
    for _ in range(6):
        s.toomany_req(sent_at=sent)
    assert s.sleep == 2.5


def test_consecutive_refused_requests_grow_the_wait_to_the_maximum():
    s = sleeper()
    seen = []
    for _ in range(9):
        s.toomany_req(sent_at=sm.arrow.now().shift(seconds=1))
        seen.append(s.sleep)
    assert seen == [2.5, 5, 10, 20, 40, 80, 160, 180, 180]


def test_an_error_soon_after_a_decay_raises_the_wait():
    s = sleeper()
    s.toomany_req()
    # no errors for a long time: the wait shrinks
    s._last_date = s._last_error = s._last_raise = ago(600)
    s._maybe_decay_sleep()
    assert round(s.sleep, 2) == 1.67
    # the decay is not a raise: this error is outside the window
    s.toomany_req()
    assert round(s.sleep, 2) == 3.33


def test_the_wait_does_not_shrink_while_errors_keep_coming():
    s = sleeper()
    s.toomany_req()
    s._last_date = s._last_raise = ago(600)
    # an error 10 s ago, from the same burst, did not change the wait
    s._last_error = ago(10)
    s._maybe_decay_sleep()
    assert s.sleep == 2.5


@pytest.fixture
def no_waiting(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(sm.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(sm.time, "sleep", waits.append)
    return waits


def manager(monkeypatch, rate_limit_tries):
    real = sm.of_env.getattr

    def getattr_(key, *args, **kwargs):
        if key == "RATE_LIMIT_NUM_TRIES":
            return rate_limit_tries
        return real(key, *args, **kwargs)

    monkeypatch.setattr(sm.of_env, "getattr", getattr_)
    monkeypatch.setattr(
        sm.settings, "get_settings", lambda: SimpleNamespace(ssl_verify="false")
    )
    return sm.sessionManager(
        retries=3,
        wait_min=0,
        wait_max=0,
        rate_limit_sleeper=sleeper(),
        forbidden_sleeper=sleeper(min_sleep=0),
    )


async def serve(handler):
    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}/"


def test_a_429_gets_more_tries_and_a_longer_wait_each_time(monkeypatch, no_waiting):
    hits = []

    async def handler(request):
        hits.append(1)
        # limited for the first 5 requests
        return web.Response(status=429 if len(hits) <= 5 else 200, text="ok")

    async def run():
        runner, url = await serve(handler)
        try:
            m = manager(monkeypatch, rate_limit_tries=8)
            async with m:
                async with m.requests_async(url, exceptions=[sm.TOO_MANY]) as r:
                    return r.status
        finally:
            await runner.cleanup()

    assert asyncio.run(run()) == 200
    assert len(hits) == 6
    # the backoff waits before tries 2 to 6
    assert [w for w in no_waiting if w >= 2.5] == [2.5, 5, 10, 20, 40]


def test_a_429_that_never_ends_stops_after_the_rate_limit_tries(
    monkeypatch, no_waiting
):
    hits = []

    async def handler(request):
        hits.append(1)
        return web.Response(status=429)

    async def run():
        runner, url = await serve(handler)
        try:
            m = manager(monkeypatch, rate_limit_tries=5)
            async with m:
                async with m.requests_async(url, exceptions=[sm.TOO_MANY]):
                    pass
        finally:
            await runner.cleanup()

    with pytest.raises(aiohttp.ClientResponseError):
        asyncio.run(run())
    assert len(hits) == 5


def test_other_errors_keep_the_usual_number_of_tries(monkeypatch, no_waiting):
    hits = []

    async def handler(request):
        hits.append(1)
        return web.Response(status=500)

    async def run():
        runner, url = await serve(handler)
        try:
            m = manager(monkeypatch, rate_limit_tries=8)
            async with m:
                async with m.requests_async(url, exceptions=[sm.TOO_MANY]):
                    pass
        finally:
            await runner.cleanup()

    with pytest.raises(aiohttp.ClientResponseError):
        asyncio.run(run())
    assert len(hits) == 3


def test_fansly_paging_gets_through_a_rate_limit(monkeypatch, no_waiting):
    """Fansly pages one request at a time through the API session, so every
    429 comes from a request sent at the current wait."""
    from ofscraper.managers.sessionmanager.ofsession import OFSessionManager
    from ofscraper.sites.fansly import api, constants

    hits = []

    async def handler(request):
        hits.append(1)
        # the second page is refused 4 times: more than the 3 usual tries
        if 2 <= len(hits) <= 5:
            return web.json_response({"success": False}, status=429)
        before = request.query.get("before")
        ids = {None: ["3", "2"], "2": ["1"]}.get(before, [])
        return web.json_response(
            {"success": True, "response": {"messages": [{"id": i} for i in ids]}}
        )

    async def run():
        app = web.Application()
        app.router.add_get("/message", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        monkeypatch.setattr(constants, "API_BASE", f"http://127.0.0.1:{port}/")
        monkeypatch.setattr(
            sm.settings, "get_settings", lambda: SimpleNamespace(ssl_verify="false")
        )
        monkeypatch.setattr(api.normalize, "messages", lambda response, extra: response["messages"])
        monkeypatch.setattr(api.normalize, "missing_account_media_ids", lambda response: [])
        try:
            m = OFSessionManager(
                wait_min=0,
                wait_max=0,
                rate_limit_sleeper=sleeper(),
                forbidden_sleeper=sleeper(min_sleep=0),
            )
            m._create_headers = lambda headers, *a: headers or {}
            m._create_cookies = lambda: None
            async with m:
                return await api.messages(m, "1")
        finally:
            await runner.cleanup()

    found = asyncio.run(run())
    assert [x["id"] for x in found] == ["3", "2", "1"]
    assert [w for w in no_waiting if w >= 2.5] == [2.5, 5, 10, 20, 20]
