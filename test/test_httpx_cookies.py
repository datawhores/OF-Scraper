import warnings

import httpx
import pytest

from ofscraper.managers.sessionmanager.sessionmanager import sessionManager


def _manager(seen):
    def handler(request):
        seen.append(request.headers.get("cookie"))
        return httpx.Response(200, json={})

    m = sessionManager.__new__(sessionManager)
    m._session = httpx.Client(transport=httpx.MockTransport(handler), cookies={"client": "1"})
    return m


def test_request_cookies_are_sent_for_that_request_only():
    seen = []
    m = _manager(seen)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        m._httpx_funct("get", url="https://onlyfans.com/api2/v2/me", cookies={"sess": "s"})
        m._httpx_funct("get", url="https://cdn.example/x")
    assert seen == ["client=1; sess=s", "client=1"]
    assert "sess" not in m._session.cookies


@pytest.mark.parametrize(
    "attributes",
    ["Path=/", "Domain=onlyfans.com; Path=/", "Domain=.onlyfans.com; Path=/"],
    ids=["host-only", "domain", "dot-domain"],
)
def test_a_cookie_the_server_sets_is_not_sent_next_to_the_requests_own(attributes):
    # the client's jar keeps what the server sets; a `sess` in it went out
    # together with the one passed for the request (aiohttp sends only the
    # request's)
    seen = []

    def handler(request):
        seen.append(request.headers.get("cookie"))
        if request.url.path == "/first":
            return httpx.Response(
                200,
                headers=[
                    ("set-cookie", f"sess=SERVER; {attributes}"),
                    ("set-cookie", "csrf=c; Path=/"),
                ],
            )
        return httpx.Response(200)

    m = sessionManager.__new__(sessionManager)
    m._session = httpx.Client(transport=httpx.MockTransport(handler))
    login = {"sess": "MINE", "auth_id": "1"}
    m._httpx_funct("get", url="https://onlyfans.com/first", cookies=login)
    m._httpx_funct("get", url="https://onlyfans.com/second", cookies=login)
    m._httpx_funct("get", url="https://onlyfans.com/third")

    assert seen[0] == "sess=MINE; auth_id=1"
    # one sess, the request's; the server's other cookies still go back
    assert sorted(seen[1].split("; ")) == ["auth_id=1", "csrf=c", "sess=MINE"]
    # the jar is left alone: a request without its own cookies gets the server's
    assert sorted(seen[2].split("; ")) == ["csrf=c", "sess=SERVER"]


def test_a_cookie_header_the_caller_wrote_is_sent_as_written():
    # httpx sends a caller's own Cookie header unchanged, even with cookies=
    seen = []
    m = _manager(seen)
    m._httpx_funct(
        "get",
        url="https://onlyfans.com/x",
        headers={"Cookie": "x=1"},
        cookies={"sess": "MINE"},
    )
    assert seen == ["x=1"]
