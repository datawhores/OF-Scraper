"""A redirect to a host outside the allowed list gets no OnlyFans login.

aiohttp follows redirects itself. On the way to another host it drops the
cookies but keeps every other header, so an allowed host that redirected to
an unlisted one sent it user-id, x-bc, app-token and the request's sign.
Two local servers stand in for the hosts: the allowed one is reached as
127.0.0.1 (added to the list), the unlisted one as localhost.
"""

import asyncio
import logging
from types import SimpleNamespace

import aiohttp
import pytest
from aiohttp import web

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.utils.host_allowlist as host_allowlist
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.ofsession import (
    OFSessionManager,
    download_session,
)

SESSION = "made-up-session-value"
LOGIN = ("user-id", "x-bc", "app-token", "sign", "time")
BODY = b"x" * 100


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            download_limit=0,
            ssl_verify="false",
            cached_disabled=True,
            anon=False,
            site="onlyfans",
        ),
    )
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)
    # the login the session adds (made-up values)
    monkeypatch.setattr(sm.auth_requests, "add_cookies", lambda: {"sess": SESSION})
    monkeypatch.setattr(
        sm.auth_requests,
        "make_headers",
        lambda: {"user-id": "1", "x-bc": "made-up", "app-token": "made-up"},
    )
    monkeypatch.setattr(
        sm.auth_requests,
        "create_sign",
        lambda url, headers: headers.update(sign="made-up", time="1"),
    )
    real = of_env.getattr

    def getattr_(key, default=None):
        if key == "MEDIA_HOST_SUFFIXES":
            return ["127.0.0.1"]
        return real(key, default)

    monkeypatch.setattr(of_env, "getattr", getattr_)
    host_allowlist._warned.clear()


def _names(headers):
    return {k.lower() for k in headers}


def _run(route, session_cls=download_session, **request):
    """Two servers; route(name, other_base) answers each request. Returns
    (result or exception, [(server, path, headers)] in order)."""
    seen = []

    async def go():
        runners = []
        bases = {}

        def handler(name):
            async def handle(request):
                seen.append((name, request.path, dict(request.headers)))
                return route(name, request.path, bases)

            return handle

        for name in ("allowed", "unlisted"):
            app = web.Application()
            app.router.add_get("/{path}", handler(name))
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            host = "127.0.0.1" if name == "allowed" else "localhost"
            bases[name] = f"http://{host}:{port}"
            runners.append(runner)
        # a second allowed host: the unlisted server reached by its address
        bases["allowed2"] = bases["unlisted"].replace("localhost", "127.0.0.1")
        try:
            async with session_cls(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                try:
                    async with c.requests_async(
                        url=f"{bases['allowed']}/start", **request
                    ) as r:
                        return (r.status, await r.read_()), seen
                except Exception as E:
                    return E, seen
        finally:
            for runner in runners:
                await runner.cleanup()

    return asyncio.run(go())


def _redirect_to(target):
    def route(name, path, bases):
        if path == "/start":
            raise web.HTTPFound(f"{bases[target]}/file")
        return web.Response(body=BODY)

    return route


def test_redirect_to_an_unlisted_host_gets_no_login(caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        result, seen = _run(_redirect_to("unlisted"))
    assert result == (200, BODY)  # still followed
    (first, path1, start), (second, path2, hop) = seen
    assert (first, path1) == ("allowed", "/start")
    assert (second, path2) == ("unlisted", "/file")
    # the allowed host got the login, the unlisted one none of it
    assert set(LOGIN) <= _names(start) and SESSION in start.get("Cookie", "")
    assert not set(LOGIN) & _names(hop)
    assert SESSION not in hop.get("Cookie", "")
    # the host only, never the link
    assert "localhost" in caplog.text and "/file" not in caplog.text


def test_caller_headers_still_go_to_the_unlisted_host():
    # a DRM segment: the caller's own Range and login Cookie header
    result, seen = _run(
        _redirect_to("unlisted"),
        headers={"Range": "bytes=10-", "Cookie": f"auth_id=1;sess={SESSION};"},
    )
    assert result == (200, BODY)
    hop = seen[1][2]
    assert hop.get("Range") == "bytes=10-"
    assert not set(LOGIN) & _names(hop)
    assert SESSION not in hop.get("Cookie", "")


def test_api_session_redirect_to_an_unlisted_host_gets_no_login():
    # the session Media.parse_mpd fetches the manifest with
    result, seen = _run(_redirect_to("unlisted"), session_cls=OFSessionManager)
    assert result == (200, BODY)
    assert set(LOGIN) <= _names(seen[0][2])
    assert not set(LOGIN) & _names(seen[1][2])


def test_redirect_to_another_allowed_host_keeps_the_login():
    result, seen = _run(_redirect_to("allowed2"))
    assert result == (200, BODY)
    assert [s[1] for s in seen] == ["/start", "/file"]
    assert set(LOGIN) <= _names(seen[1][2])


def test_redirect_on_the_same_host_keeps_the_login():
    result, seen = _run(_redirect_to("allowed"))
    assert result == (200, BODY)
    assert [(s[0], s[1]) for s in seen] == [("allowed", "/start"), ("allowed", "/file")]
    hop = seen[1][2]
    assert set(LOGIN) <= _names(hop) and SESSION in hop.get("Cookie", "")


def test_no_redirects_asked_for_is_unchanged():
    result, seen = _run(_redirect_to("unlisted"), redirects=False)
    assert result[0] == 302
    assert len(seen) == 1


def _loop(name, path, bases):
    # allowed and unlisted send the request back and forth forever
    other = "unlisted" if name == "allowed" else "allowed"
    raise web.HTTPFound(f"{bases[other]}/next")


def test_redirect_loop_still_stops_at_the_limit():
    result, seen = _run(_loop)
    assert isinstance(result, aiohttp.TooManyRedirects)
    # aiohttp's limit: 10 redirects
    assert len(seen) == 10
    for name, _, headers in seen:
        if name == "unlisted":
            assert not set(LOGIN) & _names(headers)
        else:
            assert set(LOGIN) <= _names(headers)
