from types import SimpleNamespace

import pytest

import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.ofsession import (
    OFSessionManager,
    SubscriptionSessionManager,
    cdm_session,
    cdm_session_manual,
    download_session,
    like_session,
    metadata_session,
)
from ofscraper.managers.sessionmanager.sleepers import sleepers


@pytest.fixture(autouse=True)
def plain_settings(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            ssl_verify="false",
            cached_disabled=True,
            download_limit=0,
            command="download",
        ),
    )


@pytest.mark.parametrize(
    "cls,rate_attr,forbidden_attr",
    [
        (OFSessionManager, "rate_limit_session_sleeper", "forbidden_session_sleeper"),
        (
            download_session,
            "download_rate_limit_session_sleeper",
            "download_forbidden_session_sleeper",
        ),
        (
            metadata_session,
            "metadata_rate_limit_session_sleeper",
            "metadata_forbidden_session_sleeper",
        ),
        (
            cdm_session_manual,
            "cdm_rate_limit_session_sleeper",
            "cdm_forbidden_session_sleeper",
        ),
        (
            like_session,
            "like_rate_limit_session_sleeper",
            "like_forbidden_session_sleeper",
        ),
        (
            SubscriptionSessionManager,
            "subscription_rate_limit_session_sleeper",
            "subscription_forbidden_session_sleeper",
        ),
    ],
)
def test_session_subclasses_resolve_default_and_override_sleepers(
    cls, rate_attr, forbidden_attr
):
    sess = cls()
    assert sess._rate_limit_sleeper is getattr(sleepers, rate_attr)
    assert sess._forbidden_sleeper is getattr(sleepers, forbidden_attr)

    custom_rate = object()
    custom_forbidden = object()
    overridden = cls(
        rate_limit_sleeper=custom_rate, forbidden_sleeper=custom_forbidden
    )
    assert overridden._rate_limit_sleeper is custom_rate
    assert overridden._forbidden_sleeper is custom_forbidden


def test_cdm_session_constructs_with_defaults():
    assert cdm_session() is not None
