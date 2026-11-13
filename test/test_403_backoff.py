"""A 403 backoff applies before the next request, whatever the rate-limit gap is (#214)."""

import asyncio

import pytest

import ofscraper.managers.sessionmanager.sessionmanager as sm


def sleeper(min_sleep, sleep=None):
    s = sm.SessionSleep(
        sleep=sleep or 1,
        min_sleep=min_sleep,
        difmin=0,
        max_sleep=100,
        decay_threshold=1000,
        decay_factor=2,
        increase_factor=2,
        error_name="test",
    )
    return s


def manager(rate_min, forbidden_min, forbidden_backoff=None, rate_backoff=None):
    m = object.__new__(sm.sessionManager)
    m._rate_limit_sleeper = sleeper(rate_min)
    m._forbidden_sleeper = sleeper(forbidden_min)
    if forbidden_backoff:
        m._forbidden_sleeper.sleep = forbidden_backoff
    if rate_backoff:
        m._rate_limit_sleeper.sleep = rate_backoff
    return m


@pytest.fixture
def waits(monkeypatch):
    recorded = []

    async def fake_async_sleep(seconds):
        recorded.append(round(seconds, 1))

    monkeypatch.setattr(sm.time, "sleep", lambda s: recorded.append(round(s, 1)))
    monkeypatch.setattr(sm.asyncio, "sleep", fake_async_sleep)
    return recorded


def run(m, use_async):
    if use_async:
        asyncio.run(m._async_wait_before_request())
    else:
        m._wait_before_request()


@pytest.mark.parametrize("use_async", [False, True])
def test_403_backoff_applies_when_the_rate_limit_gap_is_set(waits, use_async):
    # the standard API's defaults: a 0.5s rate-limit gap, no 403 gap
    m = manager(rate_min=0.5, forbidden_min=0, forbidden_backoff=8)
    run(m, use_async)
    assert 8 in waits


@pytest.mark.parametrize("use_async", [False, True])
def test_403_backoff_applies_during_a_rate_limit_backoff(waits, use_async):
    m = manager(rate_min=0, forbidden_min=0, forbidden_backoff=8, rate_backoff=3)
    run(m, use_async)
    assert waits == [3, 8]


@pytest.mark.parametrize("use_async", [False, True])
def test_no_403_backoff_means_no_extra_wait(waits, use_async):
    # the 403 pacing gap still only applies when the rate-limit sleeper didn't pace
    m = manager(rate_min=0.5, forbidden_min=2)
    m._rate_limit_sleeper._last_request_time = sm.arrow.now()
    run(m, use_async)
    assert all(w <= 0.5 for w in waits)


@pytest.mark.parametrize("use_async", [False, True])
def test_403_gap_applies_when_there_is_no_rate_limit_gap(waits, use_async):
    m = manager(rate_min=0, forbidden_min=2)
    m._forbidden_sleeper._last_request_time = sm.arrow.now()
    run(m, use_async)
    assert len(waits) == 1 and 1.5 < waits[0] <= 2
