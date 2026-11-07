"""Review fixes for the Fansly site PR.

1. With the default ssl_verify "custom", every session builds the custom SSL
   context, which seeded its cipher order from the OnlyFans auth.json through
   the interactive reader. A Fansly-only profile was asked for OnlyFans auth.
2. Failed requests log their headers. The Fansly token in `authorization`
   wasn't registered for redaction, so it reached the debug log unmasked.
"""

import base64
import json

import pytest

import ofscraper.managers.sessionmanager.cert as cert
import ofscraper.sites as sites
import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.utils.logs.classes.classes import SensitiveFormatter

# base64 of "<session id>:1:2:<rest>"; ">>>" and "???" encode to "+" and "/",
# so the token holds regex characters and the escape matters
TOKEN = base64.b64encode(b"123456789012345678:1:2:abcdef>>>???0123456789").decode()
assert "+" in TOKEN and "/" in TOKEN


@pytest.fixture
def onlyfans_reads(monkeypatch):
    calls = []

    def read_auth():
        calls.append(1)
        return {"auth_id": "11111"}

    monkeypatch.setattr(cert.auth_requests.auth_file, "read_auth", read_auth)
    monkeypatch.setattr(cert, "_CONFIG_CACHE", {})
    return calls


def test_fansly_profile_never_reads_onlyfans_auth(monkeypatch, onlyfans_reads):
    monkeypatch.setattr(sites, "is_fansly", lambda: True)
    monkeypatch.setattr(
        fansly_auth, "read_auth", lambda path=None: {"authorization_token": TOKEN}
    )
    cert.create_custom_ssl_context()
    assert onlyfans_reads == []
    (seed,) = cert._CONFIG_CACHE
    assert seed.startswith("fansly_")
    # the seed's start is logged: it must not carry the session id itself
    assert fansly_auth.session_id(TOKEN) not in seed


def test_fansly_profile_without_auth_gets_a_default_seed(monkeypatch, onlyfans_reads):
    monkeypatch.setattr(sites, "is_fansly", lambda: True)
    monkeypatch.setattr(fansly_auth, "read_auth", lambda path=None: fansly_auth.empty())
    cert.create_custom_ssl_context()
    assert onlyfans_reads == []
    assert list(cert._CONFIG_CACHE) == ["fansly_default_seed"]


def test_onlyfans_seed_is_unchanged(monkeypatch, onlyfans_reads):
    monkeypatch.setattr(sites, "is_fansly", lambda: False)
    cert.create_custom_ssl_context()
    assert onlyfans_reads == [1]
    assert list(cert._CONFIG_CACHE) == ["11111"]


@pytest.fixture
def clean_patterns(monkeypatch):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: None)
    fansly_auth._cache.update(path=None, mtime=None, auth=None)
    yield
    fansly_auth._cache.update(path=None, mtime=None, auth=None)


def test_token_is_masked_in_logs_once_auth_is_read(tmp_path, clean_patterns):
    path = tmp_path / "fansly_auth.json"
    path.write_text(
        json.dumps({"authorization_token": TOKEN, "user_agent": "x" * 50}),
        encoding="utf-8",
    )
    fansly_auth.read_auth(path)
    line = SensitiveFormatter()._filter(
        f"request headers {{'authorization': '{TOKEN}', 'origin': 'https://fansly.com'}}"
    )
    assert TOKEN not in line
    assert "{fansly_token}" in line
    assert "https://fansly.com" in line


def test_placeholder_or_empty_token_adds_no_pattern(clean_patterns):
    fansly_auth.hide_token("")
    fansly_auth.hide_token(fansly_auth.PLACEHOLDER)
    assert sensitive._USER_ADDED_PATTERNS == {}


@pytest.mark.parametrize("fansly", [True, False])
def test_auth_check_fetches_the_onlyfans_rule_only_for_onlyfans(monkeypatch, fansly):
    # the auth check fetches OnlyFans' dynamic rule before /me. Fansly requests
    # aren't signed with it, so a Fansly profile mustn't depend on GitHub
    from types import SimpleNamespace

    import ofscraper.data.api.init as init

    fetches = []
    monkeypatch.setattr(sites, "is_fansly", lambda: fansly)
    monkeypatch.setattr(
        init.settings, "get_settings", lambda: SimpleNamespace(anon=False)
    )
    monkeypatch.setattr(
        init.auth_requests, "get_request_auth", lambda: fetches.append(1)
    )
    monkeypatch.setattr(init.me, "scrape_user", lambda: {"isAuth": True})
    assert init.getstatus() == "UP"
    assert fetches == ([] if fansly else [1])
