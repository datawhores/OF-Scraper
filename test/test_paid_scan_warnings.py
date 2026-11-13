import asyncio
import logging
from contextlib import asynccontextmanager

import pytest

import ofscraper.data.api.paid as paid


class _Response:
    def __init__(self, status, data):
        self.status = status
        self._data = data

    async def json_(self):
        return self._data


class _Client:
    def __init__(self, status=200, data=None, exc=None):
        self.status, self.data, self.exc = status, data, exc

    @asynccontextmanager
    async def requests_async(self, url):
        if self.exc:
            raise self.exc
        yield _Response(self.status, self.data)


@pytest.fixture
def warnings_seen(monkeypatch):
    monkeypatch.setattr(paid.progress_utils.api, "add_job_task", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(paid.log, "traceback_", lambda *a, **k: None, raising=False)
    seen = []

    class Capture(logging.Handler):
        def emit(self, record):
            if record.levelno == logging.WARNING:
                seen.append(record.getMessage())

    handler = Capture()
    paid.log.addHandler(handler)
    yield seen
    paid.log.removeHandler(handler)


def _scans(client):
    async def per_model():
        return [b async for b in paid.scrape_paid(client, "model")]

    async def all_models():
        return [b async for b in paid.scrape_all_paid(client)]

    return {"per-model": per_model, "all-models": all_models}


@pytest.mark.parametrize("scan", ["per-model", "all-models"])
@pytest.mark.parametrize(
    "client,reason",
    [
        (_Client(status=403), "HTTP 403"),
        (_Client(data=["not", "a", "dict"]), "unexpected response format"),
        (_Client(exc=OSError("connection reset")), "connection reset"),
    ],
    ids=["http-error", "bad-format", "exception"],
)
def test_early_stop_warns(warnings_seen, scan, client, reason):
    assert asyncio.run(_scans(client)[scan]()) == []
    assert len(warnings_seen) == 1
    assert reason in warnings_seen[0] and "Purchases may be incomplete" in warnings_seen[0]


def _failed_request(cls):
    # what sessionmanager raises after the retries: the error carries the
    # request it was for, headers included (#243)
    from aiohttp import RequestInfo
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL

    url = URL("https://example.invalid/api2/v2/posts/paid")
    headers = CIMultiDictProxy(
        CIMultiDict(
            {
                "x-bc": "fake-xbc-in-header",
                "user-id": "fake-user-id",
                "sign": "fake-sign-in-header",
                "Cookie": "auth_id=fake-user-id; sess=fake-sess-in-cookie",
            }
        )
    )
    info = RequestInfo(url, "GET", headers, url)
    return cls(info, (), status=429, message="Too Many Requests")


@pytest.mark.parametrize("scan", ["per-model", "all-models"])
@pytest.mark.parametrize("error", ["ClientResponseError", "ContentTypeError"])
def test_failed_request_warning_leaves_out_the_request_headers(warnings_seen, scan, error):
    import aiohttp

    client = _Client(exc=_failed_request(getattr(aiohttp, error)))
    assert asyncio.run(_scans(client)[scan]()) == []
    assert len(warnings_seen) == 1
    warning = warnings_seen[0]
    for secret in ("fake-xbc-in-header", "fake-user-id", "fake-sign-in-header", "fake-sess-in-cookie"):
        assert secret not in warning
    # still says what went wrong
    assert error in warning and "429" in warning and "Too Many Requests" in warning


@pytest.mark.parametrize("scan", ["per-model", "all-models"])
def test_normal_page_is_yielded_without_warning(warnings_seen, scan):
    client = _Client(data={"list": [{"id": 1}], "hasMore": False})
    assert asyncio.run(_scans(client)[scan]()) == [[{"id": 1}]]
    assert warnings_seen == []
