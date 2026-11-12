"""A rejected signed CDN link must escape both request and download retries."""

import asyncio
from types import SimpleNamespace

import aiohttp
import httpx
import pytest
from multidict import CIMultiDict, CIMultiDictProxy
from tenacity import stop_after_attempt, wait_none
from yarl import URL

import ofscraper.managers.sessionmanager.sessionmanager as sm
from ofscraper.commands.scraper.actions.download.utils.retries import download_retry


SIGNED = "https://cdn2.onlyfans.com/dash/files/example/x.mpd"
SIGNING = {"Policy": "example", "Signature": "example", "Key-Pair-Id": "example"}
BODY = "<Error><Code>AccessDenied</Code><Message>Access denied</Message></Error>"
QUIET = SimpleNamespace(debug=lambda *a: None, traceback_=lambda *a: None)


@pytest.fixture
def setup_request(monkeypatch):
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(sm.asyncio, "sleep", sleep)
    monkeypatch.setattr(sm.time, "sleep", waits.append)
    monkeypatch.setattr(sm.sessionManager, "_get_ssl_context", lambda self: False)
    monkeypatch.setattr(sm.sessionManager, "print_auth_warning", lambda *a: None)

    def setup(use_async, initial_sleep=0, status=403, missing_request=False):
        forbidden = sm.SessionSleep(
            sleep=15, min_sleep=0, difmin=0, max_sleep=1000,
            decay_threshold=1000, decay_factor=2, increase_factor=2,
        )
        forbidden.sleep = initial_sleep
        rate = sm.SessionSleep(min_sleep=0)
        m = sm.sessionManager(
            retries=3, wait_min=0, wait_max=0, log=QUIET, sem_count=1,
            forbidden_sleeper=forbidden, rate_limit_sleeper=rate,
        )
        replies = []
        errors = []

        def response(url, params):
            request = httpx.Request("GET", url, params=params)
            raw = httpx.Response(
                status, request=request, text=BODY,
                headers={"Server": "CloudFront", "X-Cache": "Error from cloudfront"},
            )
            if use_async:
                info = aiohttp.RequestInfo(
                    URL(str(request.url)), "GET", CIMultiDictProxy(CIMultiDict()),
                    URL(str(request.url)),
                )
                error = aiohttp.ClientResponseError(info, (), status=status)
            else:
                error = httpx.HTTPStatusError("Forbidden", request=request, response=raw)
            if missing_request:
                if use_async:
                    del error.request_info
                else:
                    error = httpx.HTTPStatusError("Forbidden", request=None, response=raw)
            errors.append(error)

            def raise_for_status():
                raise error

            async def text():
                return BODY

            reply = SimpleNamespace(
                ok=False, status_code=status, url=request.url, headers=raw.headers,
                request=request, text_=text if use_async else lambda: BODY,
                raise_for_status=raise_for_status, closed=False,
            )

            def close():
                reply.closed = True

            reply.close = close
            replies.append(reply)
            return reply

        async def async_request(method, url, params=None, **kwargs):
            return response(url, params)

        def sync_request(method, url, params=None, **kwargs):
            return response(url, params)

        monkeypatch.setattr(m, "_aio_funct", async_request)
        monkeypatch.setattr(m, "_httpx_funct", sync_request)
        return m, replies, errors, waits

    return setup


def fetch(m, use_async, url, params=None, outer_retry=False):
    async def run():
        if outer_retry:
            async for attempt in download_retry(stop=stop_after_attempt(3), wait=wait_none()):
                with attempt:
                    async with m.requests_async(url, params=params, exceptions=[sm.FORBIDDEN]):
                        pytest.fail("403 reached response consumer")
        else:
            async with m.requests_async(url, params=params, exceptions=[sm.FORBIDDEN]):
                pytest.fail("403 reached response consumer")

    if use_async:
        asyncio.run(run())
    else:
        with m.requests(url, params=params, exceptions=[sm.FORBIDDEN]):
            pytest.fail("403 reached response consumer")


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("initial_sleep", [0, 7])
@pytest.mark.parametrize("separate_params", [False, True])
def test_signed_cdn_403_raises_once_without_changing_backoff(
    setup_request, use_async, initial_sleep, separate_params,
):
    m, replies, errors, _ = setup_request(use_async, initial_sleep)
    url = SIGNED if separate_params else str(URL(SIGNED).with_query(SIGNING))
    with pytest.raises((aiohttp.ClientResponseError, httpx.HTTPStatusError)) as caught:
        fetch(m, use_async, url, SIGNING if separate_params else None)
    assert len(replies) == 1
    assert m._forbidden_sleeper.sleep == initial_sleep
    assert caught.value is errors[0]
    if use_async:
        assert replies[0].closed
        assert m._sem._value == 1


def test_signed_cdn_403_escapes_outer_download_retry(setup_request):
    m, replies, errors, _ = setup_request(True)
    with pytest.raises(aiohttp.ClientResponseError) as caught:
        fetch(m, True, SIGNED, SIGNING, outer_retry=True)
    assert len(replies) == 1
    assert m._forbidden_sleeper.sleep == 0
    assert caught.value is errors[0]


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("url,params", [
    ("https://onlyfans.com/api2/v2/users/me", None),
    ("https://onlyfans.com/api2/v2/users/me", SIGNING),
    (SIGNED, {"Policy": "example"}),
    ("https://example.com/file", SIGNING),
])
def test_other_403_still_retries_and_backs_off(setup_request, use_async, url, params):
    m, replies, errors, waits = setup_request(use_async)
    with pytest.raises((aiohttp.ClientResponseError, httpx.HTTPStatusError)) as caught:
        fetch(m, use_async, url, params)
    assert len(replies) == 3
    assert m._forbidden_sleeper.sleep == 60
    assert 15 in waits and 30 in waits
    assert caught.value is errors[-1]


@pytest.mark.parametrize("use_async", [False, True])
def test_403_without_request_still_retries_and_backs_off(setup_request, use_async):
    m, replies, errors, waits = setup_request(use_async, missing_request=True)
    with pytest.raises((aiohttp.ClientResponseError, httpx.HTTPStatusError)) as caught:
        fetch(m, use_async, SIGNED, SIGNING)
    assert all(sm.is_provided_exception_number(error, 403) for error in errors)
    assert all(sm.is_signed_cdn_forbidden(error) is False for error in errors)
    assert len(replies) == 3
    assert m._forbidden_sleeper.sleep == 60
    assert 15 in waits and 30 in waits
    assert caught.value is errors[-1]


@pytest.mark.parametrize("use_async", [False, True])
def test_signed_cdn_500_still_retries(setup_request, use_async):
    m, replies, _, _ = setup_request(use_async, status=500)
    with pytest.raises((aiohttp.ClientResponseError, httpx.HTTPStatusError)):
        fetch(m, use_async, SIGNED, SIGNING)
    assert len(replies) == 3
    assert m._forbidden_sleeper.sleep == 0
