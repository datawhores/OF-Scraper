import ast
import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers


class _Response:
    ok = True
    status = 200
    headers = {}

    def text_(self):
        return ""

    async def json_(self):
        return {"message": "kid:key"}


class _Session:
    def __init__(self):
        self.calls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, **kw):
        self.calls.append(kw)
        yield _Response()

    @contextlib.contextmanager
    def requests(self, **kw):
        self.calls.append(kw)
        yield _Response()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_cdrm_headers_are_a_python_literal(monkeypatch):
    monkeypatch.setattr(
        keyhelpers.auth_requests,
        "make_headers",
        lambda: {"user-agent": "ua", "x-bc": "abc"},
    )
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", lambda: "a=1; b=2")
    monkeypatch.setattr(
        keyhelpers.auth_requests,
        "create_sign",
        lambda url, headers: headers.update({"sign": "s"}),
    )
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    monkeypatch.setattr(keyhelpers, "log", logging.getLogger("test"))
    session = _Session()

    key = asyncio.run(keyhelpers.key_helper_cdrm(session, "pssh", "https://lic", 1))

    assert key == "kid:key"
    sent = session.calls[0]["json"]["headers"]
    # cdrm-project reads this field with ast.literal_eval (#43)
    assert ast.literal_eval(sent) == {
        "user-agent": "ua",
        "x-bc": "abc",
        "cookie": "a=1; b=2",
        "sign": "s",
    }
