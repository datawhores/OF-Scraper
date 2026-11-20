"""The auth check gives its reason to callers.

Given/When/Then:
1. Given /me answers, when auth_status() runs, then it returns UP or DOWN
   with no message, and getstatus() still returns only the status.
2. Given the auth can't be checked (a network error, or no usable dynamic
   rule), then auth_status() returns UNAVAILABLE with the reason, and
   check_auth() raises AuthCheckUnavailable carrying that reason, without
   asking for the auth again.
"""

from types import SimpleNamespace

import httpx
import pytest

import ofscraper.data.api.init as init
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.checkers as checkers


class AuthPrompted(Exception):
    pass


@pytest.fixture
def me_answers(monkeypatch):
    """/me answers with the given reply, or raises the given error."""
    monkeypatch.setattr(
        init.settings, "get_settings", lambda: SimpleNamespace(anon=False)
    )
    monkeypatch.setattr(init.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(init.auth_requests, "get_request_auth", lambda: None)
    monkeypatch.setattr(init.log, "traceback_", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(checkers.auth_file, "read_auth", lambda: {})

    def make_auth(*args, **kwargs):
        raise AuthPrompted

    monkeypatch.setattr(checkers.make, "make_auth", make_auth)

    def answer(reply):
        def scrape_user():
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(init.me, "scrape_user", scrape_user)

    return answer


TIMEOUT = httpx.ConnectTimeout(
    "timed out", request=httpx.Request("GET", "https://onlyfans.com/api2/v2/users/me")
)


def _rejected(status):
    request = httpx.Request("GET", "https://onlyfans.com/api2/v2/users/me")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


# 1. /me answers


@pytest.mark.parametrize(
    "reply,status",
    [
        ({"isAuth": True}, "UP"),
        ({"isAuth": False}, "DOWN"),
        (_rejected(401), "DOWN"),
    ],
    ids=["logged-in", "logged-out", "rejected"],
)
def test_answered_check_has_no_message(me_answers, reply, status):
    me_answers(reply)
    assert init.auth_status() == (status, None)
    assert init.getstatus() == status


def test_anonymous_run_is_up(monkeypatch):
    monkeypatch.setattr(
        init.settings, "get_settings", lambda: SimpleNamespace(anon=True)
    )
    assert init.auth_status() == ("UP", None)


# 2. the auth can't be checked


def test_network_failure_gives_the_reason(me_answers):
    me_answers(TIMEOUT)
    status, message = init.auth_status()
    assert status == "UNAVAILABLE"
    assert message.startswith("Couldn't reach onlyfans.com (timed out)")
    assert init.getstatus() == "UNAVAILABLE"

    with pytest.raises(checkers.AuthCheckUnavailable) as raised:
        checkers.check_auth()
    assert str(raised.value) == f"Couldn't check the auth: {message}"


def test_no_usable_dynamic_rule_gives_each_reason(me_answers, monkeypatch):
    me_answers({"isAuth": True})
    unusable = auth_requests.UnusableDynamicRule("unusable rule: missing format")

    def get_request_auth():
        raise auth_requests.DynamicRuleUnavailable(
            [("xagler", unusable), ("digitalcriminals", TIMEOUT)]
        )

    monkeypatch.setattr(init.auth_requests, "get_request_auth", get_request_auth)

    status, message = init.auth_status()
    assert status == "UNAVAILABLE"
    assert "xagler: unusable rule: missing format" in message
    assert "digitalcriminals: couldn't reach onlyfans.com (timed out)" in message
    assert "This isn't a problem with your auth" in message

    # not reported as bad auth: no auth prompt
    with pytest.raises(checkers.AuthCheckUnavailable) as raised:
        checkers.check_auth()
    assert "xagler: unusable rule: missing format" in str(raised.value)
