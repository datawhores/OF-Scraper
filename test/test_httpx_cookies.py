import warnings

import httpx

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
