"""A redirect to a host outside the allowed list gets no OnlyFans login, on the
sync (httpx) path too.

httpx follows redirects itself. On the way to another host it drops
Authorization and the request's cookies but keeps every other header, so an
allowed host that redirected to an unlisted one sent it user-id, x-bc,
app-token and the request's sign. Two local servers stand in for the hosts:
the allowed one is reached as 127.0.0.1 (added to the list), the unlisted one
as localhost. Same setup as test_redirect_login.py, which covers aiohttp.
"""

import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.utils.host_allowlist as host_allowlist
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.ofsession import OFSessionManager

SESSION = "made-up-session-value"
LOGIN = ("user-id", "x-bc", "app-token", "sign", "time")
BODY = b"x" * 100


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


class _Server6(ThreadingHTTPServer):
    address_family = socket.AF_INET6


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            ssl_verify="false",
            cached_disabled=True,
            anon=False,
            site="onlyfans",
        ),
    )
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
    # the session waits a second on close
    monkeypatch.setattr(sm, "time", SimpleNamespace(sleep=lambda s: None))
    host_allowlist._warned.clear()


def _names(headers):
    return {k.lower() for k in headers}


def _run(route, **request):
    """Two servers; route(name, path, bases) returns (status, location or
    None) for each request. Returns (result or exception, [(server, path,
    headers)] in order)."""
    seen = []
    lock = threading.Lock()
    servers = []
    bases = {}

    def handler(name):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                with lock:
                    seen.append((name, self.path, dict(self.headers)))
                status, location = route(name, self.path, bases)
                self.send_response(status)
                if location:
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_header("Content-Length", str(len(BODY)))
                self.end_headers()
                self.wfile.write(BODY)

            def log_message(self, *args):
                pass

        return Handler

    def serve(server):
        threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        servers.append(server)

    for name in ("allowed", "unlisted"):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler(name))
        serve(server)
        port = server.server_address[1]
        host = "127.0.0.1" if name == "allowed" else "localhost"
        bases[name] = f"http://{host}:{port}"
    # localhost may resolve to ::1 first: answer there too, or each connect
    # waits for the refusal (about a second on Windows)
    try:
        serve(_Server6(("::1", port), handler("unlisted")))
    except OSError:
        pass
    # a second allowed host: the unlisted server reached by its address
    bases["allowed2"] = bases["unlisted"].replace("localhost", "127.0.0.1")
    try:
        with OFSessionManager(
            retries=1, wait_min=0, wait_max=0, log=_Log()
        ) as c:
            try:
                with c.requests(url=f"{bases['allowed']}/start", **request) as r:
                    return (r.status_code, r.read()), seen
            except Exception as E:
                return E, seen
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


def _redirect_to(target):
    def route(name, path, bases):
        if path == "/start":
            return 302, f"{bases[target]}/file"
        return 200, None

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
    result, seen = _run(_redirect_to("unlisted"), headers={"Range": "bytes=10-"})
    assert result == (200, BODY)
    hop = seen[1][2]
    assert hop.get("Range") == "bytes=10-"
    assert not set(LOGIN) & _names(hop)


def test_redirect_to_another_allowed_host_keeps_the_login():
    result, seen = _run(_redirect_to("allowed2"))
    assert result == (200, BODY)
    assert [s[1] for s in seen] == ["/start", "/file"]
    assert set(LOGIN) <= _names(seen[1][2])


def test_redirect_on_the_same_host_keeps_the_login():
    # (httpx sends a redirect only the client's own cookies, on any host;
    # that is unchanged)
    result, seen = _run(_redirect_to("allowed"))
    assert result == (200, BODY)
    assert [(s[0], s[1]) for s in seen] == [("allowed", "/start"), ("allowed", "/file")]
    assert set(LOGIN) <= _names(seen[1][2])


def test_no_redirects_asked_for_is_unchanged():
    result, seen = _run(_redirect_to("unlisted"), redirects=False)
    assert result[0] == 302
    assert len(seen) == 1


def test_fansly_is_not_checked(monkeypatch):
    # Fansly adds its own headers and isn't on the OnlyFans list
    monkeypatch.setattr(sm.sites, "is_fansly", lambda: True)
    monkeypatch.setattr(
        sm.fansly_headers, "make_headers", lambda url: {"x-made-up": "1"}
    )
    result, seen = _run(_redirect_to("unlisted"))
    assert result == (200, BODY)
    assert "x-made-up" in _names(seen[1][2])


def _loop(name, path, bases):
    # allowed and unlisted send the request back and forth forever
    other = "unlisted" if name == "allowed" else "allowed"
    return 302, f"{bases[other]}/next"


def test_redirect_loop_still_stops_at_the_limit():
    result, seen = _run(_loop)
    assert isinstance(result, httpx.TooManyRedirects)
    # httpx's limit: 20 redirects, so 21 requests
    assert len(seen) == 21
    assert set(LOGIN) <= _names(seen[0][2])
    # httpx builds each hop from the one before, so once the login is
    # dropped it stays dropped, back on the allowed host too
    for name, _, headers in seen[1:]:
        assert not set(LOGIN) & _names(headers)
