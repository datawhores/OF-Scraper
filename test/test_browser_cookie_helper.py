"""browser_cookie_helper reads the browser's cookies without the requests package."""

import builtins
import http.cookiejar
import importlib
import sys

import ofscraper.utils.auth.utils.prompt as auth_prompt


def _cookie(name, value):
    return http.cookiejar.Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=".onlyfans.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
    )


def test_browser_cookie_helper_without_requests(monkeypatch):
    # Make `import requests` fail, then reload the module so it is imported
    # the way it would be in an environment without requests.
    real_import = builtins.__import__

    def no_requests(name, *args, **kwargs):
        if name == "requests" or name.startswith("requests."):
            raise ImportError("requests is not installed")
        return real_import(name, *args, **kwargs)

    for name in [m for m in sys.modules if m == "requests" or m.startswith("requests.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(builtins, "__import__", no_requests)
    module = importlib.reload(auth_prompt)
    monkeypatch.setattr(builtins, "__import__", real_import)

    seen = {}

    def fake_browser(domain_name):
        seen["domain_name"] = domain_name
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(_cookie("sess", "sess-value"))
        jar.set_cookie(_cookie("auth_id", "424242"))
        jar.set_cookie(_cookie("other", "ignored"))
        return jar

    monkeypatch.setattr(module.browser_cookie3, "chrome", fake_browser, raising=False)
    monkeypatch.setattr(module.prompts, "xbc_prompt", lambda current: "xbc-value")
    monkeypatch.setattr(module.prompts, "user_agent_prompt", lambda current: "ua")
    monkeypatch.setattr(module.console, "print", lambda *a, **k: None)

    auth = {"sess": "", "auth_id": "", "auth_uid": "", "x-bc": "", "user_agent": ""}
    module.browser_cookie_helper(auth, "Chrome")

    assert seen["domain_name"] == "onlyfans"
    assert auth["sess"] == "sess-value"
    assert auth["auth_id"] == "424242"
    # A cookie the browser doesn't have stays empty.
    assert auth["auth_uid"] == ""
    assert auth["x-bc"] == "xbc-value"
    assert auth["user_agent"] == "ua"


def test_browser_cookie_helper_keeps_existing_values(monkeypatch):
    jar = http.cookiejar.CookieJar()
    jar.set_cookie(_cookie("sess", "from-browser"))
    jar.set_cookie(_cookie("auth_id", "from-browser-id"))
    monkeypatch.setattr(
        auth_prompt.browser_cookie3, "firefox", lambda domain_name: jar, raising=False
    )
    monkeypatch.setattr(auth_prompt.prompts, "xbc_prompt", lambda current: current)
    monkeypatch.setattr(auth_prompt.prompts, "user_agent_prompt", lambda current: current)
    monkeypatch.setattr(auth_prompt.console, "print", lambda *a, **k: None)

    auth = {"sess": "already-set", "auth_id": "", "auth_uid": "", "x-bc": "x", "user_agent": "u"}
    auth_prompt.browser_cookie_helper(auth, "Firefox")

    assert auth["sess"] == "already-set"
    assert auth["auth_id"] == "from-browser-id"


def test_browser_choice_fills_the_saved_auth_layout(monkeypatch):
    """
    The menu passes the auth in the layout auth.json uses, whose key is
    auth_uid. The helper read auth_uid_ from it (KeyError) and returned
    nothing for the caller to save.
    """
    import ofscraper.utils.auth.schema as auth_schema
    import ofscraper.utils.auth.utils.dict as auth_dict

    jar = http.cookiejar.CookieJar()
    jar.set_cookie(_cookie("sess", "sess-value"))
    jar.set_cookie(_cookie("auth_id", "424242"))
    jar.set_cookie(_cookie("auth_uid_424242", "2fa-value"))
    monkeypatch.setattr(
        auth_prompt.browser_cookie3, "chrome", lambda domain_name: jar, raising=False
    )
    monkeypatch.setattr(auth_prompt.prompts, "xbc_prompt", lambda current: "xbc")
    monkeypatch.setattr(auth_prompt.prompts, "user_agent_prompt", lambda current: "ua")
    monkeypatch.setattr(auth_prompt.console, "print", lambda *a, **k: None)

    auth = auth_schema.auth_schema(auth_dict.get_empty())
    result = auth_prompt.browser_cookie_helper(auth, "Chrome")

    assert result == {
        "sess": "sess-value",
        "auth_id": "424242",
        "auth_uid": "2fa-value",
        "user_agent": "ua",
        "x-bc": "xbc",
    }
