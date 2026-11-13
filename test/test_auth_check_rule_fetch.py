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
        lambda: SimpleNamespace(anon=False, dynamic_rules="datawhores"),
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

    monkeypatch.setattr(auth_requests, "get_request_auth_datawhores", fetch_rule)

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
    assert len(rule_host_down) == 1
