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
    settings = SimpleNamespace(anon=False, dynamic_rules="datawhores")
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

    assert "The dynamic rule (datawhores) is unusable" in caplog.text
    assert detail in caplog.text
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
