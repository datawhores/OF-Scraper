"""Pin what OnlyFans requests carry, so adding other sites can't change it.

The expected values below were recorded from ``main`` before any site
routing existed. They must keep passing unchanged.
"""

import json
from types import SimpleNamespace

import pytest

import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.config.schema as config_schema
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager import ofsession
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

FAKE_AUTH = {
    "sess": "sess-value-0001",
    "auth_id": "424242",
    "auth_uid": "",
    "user_agent": "Mozilla/5.0 (pin test) Gecko/20100101 Firefox/140.0",
    "x-bc": "xbc-value-0001",
}
FAKE_RULES = ("static-param", "41:{}:{:x}:6618", [1, 3, 5, 7, 11], 7)
URL = "https://onlyfans.com/api2/v2/users/12345/posts?limit=100&order=publish_date_asc"

EXPECTED_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "app-token": "33d57ade8c02dbc5a333db99ff9ae26a",
    "user-id": "424242",
    "x-bc": "xbc-value-0001",
    "referer": "https://onlyfans.com",
    "user-agent": "Mozilla/5.0 (pin test) Gecko/20100101 Firefox/140.0",
    "sign": "41:5acda7342877a82eca7595d139978392d65d072d:16e:6618",
    "time": "1700000000123",
}
EXPECTED_COOKIES = {"sess": "sess-value-0001", "auth_id": "424242", "auth_uid_": "424242"}


@pytest.fixture
def onlyfans_profile(monkeypatch):
    real = settings.get_settings()
    # site set explicitly: the developer's own profile may be a Fansly one
    stub = SimpleNamespace(
        **{**dict(real), "anon": False, "dynamic_rules": "datawhores", "site": "onlyfans"}
    )
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    monkeypatch.setattr(auth_requests.auth_file, "read_auth", lambda: dict(FAKE_AUTH))
    monkeypatch.setattr(auth_requests, "get_request_auth", lambda: FAKE_RULES)
    monkeypatch.setattr(auth_requests, "time", SimpleNamespace(time=lambda: 1700000000.123))
    return stub


def _bare(cls):
    return cls.__new__(cls)


@pytest.mark.parametrize(
    "cls",
    [sessionManager, ofsession.OFSessionManager, ofsession.download_session,
     ofsession.metadata_session, ofsession.like_session],
)
def test_onlyfans_signed_headers_are_unchanged(onlyfans_profile, cls):
    headers = _bare(cls)._create_headers(None, URL, True, False)
    assert headers == EXPECTED_HEADERS


@pytest.mark.parametrize(
    "cls", [sessionManager, ofsession.OFSessionManager, ofsession.download_session]
)
def test_onlyfans_cookies_are_unchanged(onlyfans_profile, cls):
    assert _bare(cls)._create_cookies() == EXPECTED_COOKIES


def test_onlyfans_unsigned_headers_are_unchanged(onlyfans_profile):
    headers = _bare(sessionManager)._create_headers({"Range": "bytes=0-"}, URL, False, False)
    expected = {k: v for k, v in EXPECTED_HEADERS.items() if k not in ("sign", "time")}
    assert headers == {"Range": "bytes=0-", **expected}


def test_onlyfans_cookie_string_is_unchanged(onlyfans_profile):
    assert auth_requests.get_cookies_str() == "auth_id=424242;sess=sess-value-0001;"


EXISTING_CONFIG = {
    "main_profile": "main_profile",
    "metadata": "{configpath}/{profile}/.data/{model_id}",
    "discord": "",
    "file_options": {
        "save_location": "/data/ofscraper",
        "dir_format": "{model_username}/{responsetype}/{mediatype}/",
        "file_format": "{filename}.{ext}",
        "textlength": 0,
        "space_replacer": " ",
        "date": "MM-DD-YYYY",
        "text_type_default": "letter",
        "truncation_default": True,
        "filename_collision": "skip",
    },
}


SECTION_KEYS = {
    "file_options": ["date", "dir_format", "file_format", "filename_collision", "save_location",
                     "space_replacer", "text_type_default", "textlength", "truncation_default"],
    "download_options": ["auto_resume", "filter", "max_post_count", "system_free_min",
                         "verify_all_integrity"],
    "binary_options": ["ffmpeg"],
    "cdm_options": ["client-id", "key-mode-default", "private-key"],
    "performance_options": ["download_limit", "download_sems"],
    "content_filter_options": ["block_ads", "file_size_max", "file_size_min", "length_max",
                               "length_min"],
    "advanced_options": ["cache-mode", "default_black_list", "default_user_list", "downloadbars",
                         "dynamic-mode-default", "env_files", "incremental_downloads",
                         "infinite_loop_action_mode", "logs_expire_time", "remove_hash_match",
                         "rotate_logs", "sanitize_text", "skip_unavailable_content", "ssl_verify",
                         "temp_dir"],
    "script_options": ["after_action_script", "after_download_script", "naming_script",
                       "post_script", "skip_download_script"],
    "responsetype": ["archived", "highlights", "message", "paid", "pinned", "profile", "stories",
                     "streams", "timeline"],
}


def test_existing_config_is_written_back_unchanged():
    """The config a current user has must rebuild to the same file."""
    first = config_schema.get_current_config_schema(dict(EXISTING_CONFIG))
    again = config_schema.get_current_config_schema(json.loads(json.dumps(first)))
    assert again == first
    # same keys as before: a new key would make config_diff rewrite users' files
    assert config_schema._config_diff_helper(json.loads(json.dumps(first)), again) is False
    assert first["file_options"] == {
        **EXISTING_CONFIG["file_options"],
    }
    assert first["metadata"] == EXISTING_CONFIG["metadata"]
    assert {k: sorted(v) for k, v in first.items() if isinstance(v, dict)} == SECTION_KEYS
    assert set(first) == {
        "main_profile", "metadata", "discord", "file_options", "download_options",
        "binary_options", "cdm_options", "performance_options",
        "content_filter_options", "advanced_options", "script_options", "responsetype",
    }
