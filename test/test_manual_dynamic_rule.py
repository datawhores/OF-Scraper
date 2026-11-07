"""OFSC_DYNAMIC_RULE_MANUAL must work when set as an environment variable.

Every value reaches the app as text, but the manual rule was used as a dict
(content.get(...)), so "manual" dynamic-rules mode always failed with
"'str' object has no attribute 'get'".
"""

import json
from types import SimpleNamespace

import pytest

import ofscraper.utils.auth.request as request
import ofscraper.utils.settings as settings

ALT_FORMAT = {
    "static_param": "abc",
    "format": "1:{}:{:x}:2",
    "checksum_indexes": [1, 2],
    "checksum_constant": 3,
}
PREFIX_FORMAT = {
    "static_param": "abc",
    "prefix": "1",
    "suffix": "2",
    "checksum_indexes": [1, 2],
    "checksum_constant": 3,
}


@pytest.fixture(autouse=True)
def fresh_auth(monkeypatch):
    monkeypatch.setattr(request, "curr_auth", None)
    monkeypatch.setattr(request, "last_check", None)
    monkeypatch.setattr(request.cache, "set", lambda *a, **k: None)


@pytest.mark.parametrize("rule", [ALT_FORMAT, PREFIX_FORMAT])
def test_manual_rule_from_the_environment_is_used(monkeypatch, rule):
    monkeypatch.setenv("DYNAMIC_RULE_MANUAL", json.dumps(rule))
    monkeypatch.setattr(
        settings, "get_settings", lambda: SimpleNamespace(dynamic_rules="manual")
    )
    static_param, fmt, indexes, constant = request.get_request_auth()
    assert static_param == "abc"
    assert fmt == "1:{}:{:x}:2"
    assert indexes == [1, 2]
    assert constant == 3


def test_the_documented_ofsc_variable_works(monkeypatch):
    # what users set; the config loader reads it into DYNAMIC_RULE_MANUAL
    monkeypatch.setenv("OFSC_DYNAMIC_RULE_MANUAL", json.dumps(ALT_FORMAT))
    request.of_env.getkeys(forced=True)
    try:
        assert request.get_request_auth_dynamic_rule_manual()[0] == "abc"
    finally:
        monkeypatch.delenv("OFSC_DYNAMIC_RULE_MANUAL")
        request.of_env.getkeys(forced=True)


def test_manual_rule_already_parsed_still_works(monkeypatch):
    monkeypatch.setattr(request.of_env, "getattr", lambda key, *a, **k: ALT_FORMAT)
    assert request.get_request_auth_dynamic_rule_manual()[0] == "abc"


@pytest.mark.parametrize("value", ["[]", "null", "42"])
def test_json_that_is_not_a_rule_says_what_is_wrong(monkeypatch, value):
    monkeypatch.setenv("DYNAMIC_RULE_MANUAL", value)
    with pytest.raises(ValueError, match="must be a JSON object"):
        request.get_request_auth_dynamic_rule_manual()


def test_invalid_json_says_what_is_wrong(monkeypatch):
    monkeypatch.setenv("DYNAMIC_RULE_MANUAL", "{not json")
    with pytest.raises(ValueError, match="OFSC_DYNAMIC_RULE_MANUAL is not valid JSON"):
        request.get_request_auth_dynamic_rule_manual()
