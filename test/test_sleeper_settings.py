import pytest

import ofscraper.utils.of_env.of_env as of_env
from ofscraper.managers.sessionmanager.sessionmanager import SessionSleep, sessionManager
from ofscraper.managers.sessionmanager.sleepers import Sleeper

PREFIXES = [
    "SESSION",
    "SESSION_403",
    "DOWNLOAD_SESSION",
    "DOWNLOAD_SESSION_403",
    "CDM_SESSION",
    "CDM_SESSION_403",
    "LIKE_SESSION",
    "LIKE_SESSION_403",
    "METADATA_SESSION",
    "METADATA_SESSION_403",
    "DISCORD_SESSION",
    "DISCORD_SESSION_403",
    "SUBSCRIPTION_SESSION",
    "SUBSCRIPTION_SESSION_403",
]

SETTINGS = {
    "_init_sleep": "SLEEP_INIT",
    "_min_sleep": "MIN_SLEEP",
    "_difmin": "SLEEP_INCREASE_TIME_DIFF",
    "_max_sleep": "SLEEP_MAX",
    "_decay_threshold": "SLEEP_DECAY_THRESHOLD",
    "_decay_factor": "SLEEP_DECAY_FACTOR",
    "_increase_factor": "SLEEP_INCREASE_FACTOR",
}


@pytest.mark.parametrize("prefix", PREFIXES)
def test_each_backoff_uses_its_own_settings(monkeypatch, prefix):
    # a distinct value per setting, so a lookup that falls back to the
    # standard API's settings shows up
    for n, suffix in enumerate(SETTINGS.values(), start=1):
        monkeypatch.setenv(f"{prefix}_{suffix}", str(1000 + n))
    sleeper = Sleeper()._create_sleeper(prefix, prefix)
    for n, (attribute, suffix) in enumerate(SETTINGS.items(), start=1):
        assert getattr(sleeper, attribute) == 1000 + n, f"{prefix}_{suffix}"


def test_a_backoff_built_without_settings_uses_the_standard_api_values():
    sleeper = SessionSleep()
    for attribute, suffix in SETTINGS.items():
        assert getattr(sleeper, attribute) == of_env.getattr(f"SESSION_{suffix}"), suffix


def test_a_session_without_backoffs_builds_both_from_settings():
    session = sessionManager()
    for prefix, sleeper in (
        ("SESSION", session._rate_limit_sleeper),
        ("SESSION_403", session._forbidden_sleeper),
    ):
        for attribute, suffix in SETTINGS.items():
            assert getattr(sleeper, attribute) == of_env.getattr(f"{prefix}_{suffix}"), f"{prefix}_{suffix}"
    # a 429 after this no longer fails comparing against a missing minimum
    session._rate_limit_sleeper.toomany_req()
    session._rate_limit_sleeper._maybe_decay_sleep()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_every_backoff_setting_has_a_default(prefix):
    for suffix in SETTINGS.values():
        assert of_env.getattr(f"{prefix}_{suffix}") is not None, f"{prefix}_{suffix}"
