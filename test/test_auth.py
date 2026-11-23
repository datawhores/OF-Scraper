"""Auth check rules, auth prompt choices, and sign status."""

# ----------------------------------------------------------------------
# From test_auth_check_broken_rule.py
# ----------------------------------------------------------------------

import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import ofscraper.data.api.init as init
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.checkers as checkers


class AuthPrompted(Exception):
    pass


@pytest.fixture
def rule_host_replies(monkeypatch):
    """The dynamic-rule host answers with the given JSON."""
    settings = SimpleNamespace(anon=False, dynamic_rules="xagler")
    monkeypatch.setattr(init.settings, "get_settings", lambda: settings)
    monkeypatch.setattr(init.log, "traceback_", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(checkers.auth_file, "read_auth", lambda: {})
    # no rule cached from an earlier check, and nothing written to the cache
    monkeypatch.setattr(auth_requests, "curr_auth", None)
    monkeypatch.setattr(auth_requests, "last_check", None)
    monkeypatch.setattr(auth_requests.cache, "set", lambda *a, **k: None)

    def make_auth(*args, **kwargs):
        raise AuthPrompted

    monkeypatch.setattr(checkers.make, "make_auth", make_auth)
    # /me signs its request, which needs the rule, and answers isAuth true
    def scrape_user():
        auth_requests.read_request_auth()
        return {"isAuth": True}

    monkeypatch.setattr(init.me, "scrape_user", scrape_user)

    def set_reply(content):
        @contextmanager
        def requests(url, *args, **kwargs):
            yield SimpleNamespace(json_=lambda: content)

        @contextmanager
        def get_session(*args, **kwargs):
            yield SimpleNamespace(requests=requests)

        monkeypatch.setattr(
            auth_requests.manager,
            "Manager",
            SimpleNamespace(session=SimpleNamespace(get_session=get_session)),
        )

    return set_reply


@pytest.mark.parametrize(
    "content,detail",
    [
        ({}, "missing static_param, format, checksum_indexes, checksum_constant"),
        (None, "expected a JSON object, got null"),
        ([], "expected a JSON object, got list"),
        ({"static_param": "a", "suffix": "s", "checksum_indexes": [1]}, "missing prefix"),
    ],
    ids=["empty-object", "null", "list", "missing-keys"],
)
def test_broken_rule_is_reported_as_unusable(rule_host_replies, caplog, content, detail):
    rule_host_replies(content)
    with caplog.at_level(logging.INFO, logger="shared"):
        with pytest.raises(checkers.AuthCheckUnavailable):
            checkers.check_auth()

    # every source sends the same reply here, so the fallbacks fail too
    assert f"xagler: unusable rule: {detail}" in caplog.text
    assert "This isn't a problem with your auth" in caplog.text
    assert "Auth Failed" not in caplog.text


def test_usable_rule_still_signs(rule_host_replies):
    rule_host_replies(
        {
            "static_param": "a",
            "format": "1:{}:{:x}:2",
            "checksum_indexes": [1, 2],
            "checksum_constant": 3,
        }
    )
    checkers.check_auth()

# ----------------------------------------------------------------------
# From test_auth_check_rule_fetch.py
# ----------------------------------------------------------------------

from types import SimpleNamespace

import httpx
import pytest

import ofscraper.data.api.init as init
import ofscraper.utils.auth.request as auth_requests

ME_RETRIES = 3


@pytest.fixture
def rule_host_down(monkeypatch):
    """The dynamic-rule host times out; /me retries like the session manager."""
    monkeypatch.setattr(
        init.settings,
        "get_settings",
        lambda: SimpleNamespace(anon=False, dynamic_rules="xagler"),
    )
    monkeypatch.setattr(init.log, "traceback_", lambda *a, **k: None, raising=False)
    # no rule cached from an earlier check
    monkeypatch.setattr(auth_requests, "curr_auth", None)
    monkeypatch.setattr(auth_requests, "last_check", None)
    fetches = []

    def fetch_rule():
        # stands for one fetch, with its own retries, through the session
        fetches.append(1)
        raise httpx.ConnectTimeout(
            "timed out",
            request=httpx.Request("GET", "https://raw.githubusercontent.com/rule"),
        )

    # the fallback sources are down too
    for source in ["xagler", *auth_requests.FALLBACK_SOURCES]:
        monkeypatch.setattr(auth_requests, f"get_request_auth_{source}", fetch_rule)

    def scrape_user():
        # each /me attempt signs its request, which needs the rule
        for attempt in range(ME_RETRIES):
            try:
                auth_requests.read_request_auth()
            except httpx.TransportError:
                if attempt == ME_RETRIES - 1:
                    raise

    monkeypatch.setattr(init.me, "scrape_user", scrape_user)
    return fetches


def test_failed_rule_fetch_is_not_repeated_by_me_retries(rule_host_down):
    assert init.getstatus() == "UNAVAILABLE"
    # one fetch from each source; the chosen one is also a fallback, asked once
    assert len(rule_host_down) == len({"xagler", *auth_requests.FALLBACK_SOURCES})

# ----------------------------------------------------------------------
# From test_auth_prompt_choice.py
# ----------------------------------------------------------------------

import pytest

import ofscraper.data.api.init as init
import ofscraper.utils.checkers as checkers
import ofscraper.utils.menu as menu


class PromptAgain(Exception):
    """The auth prompt came back after the user left it."""


@pytest.fixture
def failed_auth(monkeypatch):
    """The auth check fails as bad auth; the auth prompt answers with `choice`."""
    monkeypatch.setattr(init, "auth_status", lambda: ("DOWN", None))
    monkeypatch.setattr(checkers.auth_file, "read_auth", lambda: {})
    calls = []

    def answer(choice):
        def make_auth(auth=None, include_main_menu=False):
            calls.append(include_main_menu)
            if len(calls) > 1:
                raise PromptAgain
            return None, choice

        monkeypatch.setattr(checkers.make, "make_auth", make_auth)
        return calls

    return answer


def test_quit_in_the_auth_prompt_quits(failed_auth):
    calls = failed_auth("quit")
    with pytest.raises(SystemExit):
        checkers.check_auth()
    assert len(calls) == 1


def test_main_in_the_auth_prompt_returns_to_the_main_menu(failed_auth, monkeypatch):
    calls = failed_auth("main")
    # main menu: pick an action and run it, then quit at the next main menu
    main_answers = iter(["action", "quit"])
    monkeypatch.setattr(menu.prompts, "main_prompt", lambda: next(main_answers))
    monkeypatch.setattr(menu.prompts, "action_prompt", lambda: "download")

    assert menu.main_menu_action() is True
    # the auth prompt offered "Go to Main Menu" and wasn't shown again
    assert calls == [True]
    assert next(main_answers, None) is None

# ----------------------------------------------------------------------
# From test_sign_status.py
# The status line printed before a scrape says what the auth check found.
# ----------------------------------------------------------------------

import pytest

import ofscraper.data.api.init as init


@pytest.mark.parametrize(
    "status, shown, not_shown",
    [
        ("UP", "UP", "DOWN"),
        ("DOWN", "DOWN", "UP"),
        # a network or server problem says nothing about the auth
        ("UNAVAILABLE", "Couldn't check", "DOWN"),
    ],
)
def test_status_line(monkeypatch, status, shown, not_shown):
    printed = []
    monkeypatch.setattr(init, "getstatus", lambda: status)
    monkeypatch.setattr(
        init.console,
        "get_shared_console",
        lambda: type("Console", (), {"print": lambda self, text: printed.append(text)})(),
    )
    init.print_sign_status()
    assert len(printed) == 1
    assert shown in printed[0]
    assert not_shown not in printed[0]
