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
    import ofscraper.utils.of_env.of_env as of_env

    real_getattr = of_env.getattr
    monkeypatch.setattr(
        of_env,
        "getattr",
        lambda key, default=None: False if key == "API_FORCE_KEY" else real_getattr(key, default),
    )
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


def test_download_session_defaults_and_overrides(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager

    from ofscraper.managers.sessionmanager import sessionmanager as sm

    seen = []

    @asynccontextmanager
    async def fake_requests_async(self, *args, **kwargs):
        seen.append(kwargs)
        yield SimpleNamespace(status=200)

    monkeypatch.setattr(sm.sessionManager, "requests_async", fake_requests_async)
    sess = download_session()

    async def run():
        async with sess.requests_async("https://example.test", actions=[]):
            pass
        async with sess.requests_async(
            "https://example.test", actions=[sm.HEADERS], exceptions=[sm.FORBIDDEN]
        ):
            pass
        async with sess.requests_async("https://example.test", exceptions=[]):
            pass

    asyncio.run(run())

    assert seen[0]["actions"] == [sm.SIGN, sm.COOKIES, sm.HEADERS]
    assert seen[0]["exceptions"] == [sm.TOO_MANY, sm.AUTH]
    assert seen[1]["actions"] == [sm.HEADERS]
    assert seen[1]["exceptions"] == [sm.FORBIDDEN]
    assert seen[2]["actions"] == [sm.SIGN, sm.COOKIES, sm.HEADERS]
    assert seen[2]["exceptions"] == []


def test_of_session_request_defaults_sync_and_async(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager, contextmanager

    from ofscraper.managers.sessionmanager import sessionmanager as sm

    async_seen = []
    sync_seen = []

    @asynccontextmanager
    async def fake_async(self, *args, **kwargs):
        async_seen.append(kwargs)
        yield SimpleNamespace(status=200)

    @contextmanager
    def fake_sync(self, *args, **kwargs):
        sync_seen.append(kwargs)
        yield SimpleNamespace(status=200)

    monkeypatch.setattr(sm.sessionManager, "requests_async", fake_async)
    monkeypatch.setattr(sm.sessionManager, "requests", fake_sync)
    sess = OFSessionManager()

    async def run():
        async with sess.requests_async("https://example.test"):
            pass
        async with sess.requests_async(
            "https://example.test", actions=[], exceptions=[]
        ):
            pass
        async with sess.requests_async("https://example.test", actions=None):
            pass

    asyncio.run(run())
    with sess.requests("https://example.test"):
        pass
    with sess.requests("https://example.test", actions=[], exceptions=[]):
        pass
    with sess.requests("https://example.test", actions=None):
        pass

    for seen in (async_seen, sync_seen):
        assert seen[0]["actions"] == [sm.SIGN, sm.COOKIES, sm.HEADERS]
        assert seen[0]["exceptions"] == [sm.TOO_MANY, sm.AUTH, sm.FORBIDDEN]
        assert seen[1]["actions"] == []
        assert seen[1]["exceptions"] == []
        assert seen[2]["actions"] is None
        assert seen[2]["exceptions"] == [sm.TOO_MANY, sm.AUTH, sm.FORBIDDEN]

