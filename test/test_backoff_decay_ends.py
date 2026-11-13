"""A rate-limit backoff ends once decay brings it low, even with no minimum gap (#218)."""

import asyncio

import pytest

import ofscraper.managers.sessionmanager.sessionmanager as sm


def sleeper(min_sleep):
    # the download defaults: no minimum gap, a 1s first wait, divided by 1.5
    return sm.SessionSleep(
        sleep=0,
        min_sleep=min_sleep,
        difmin=0,
        max_sleep=100,
        decay_threshold=60,
        decay_factor=1.5,
        increase_factor=2,
        error_name="test",
    )


def decay_fully(s, rounds=40):
    for _ in range(rounds):
        # well past the decay threshold, never on its boundary
        s._last_date = sm.arrow.now().shift(seconds=-120)
        s._maybe_decay_sleep()


@pytest.fixture
def waits(monkeypatch):
    recorded = []

    async def fake_async_sleep(seconds):
        recorded.append(round(seconds, 1))

    monkeypatch.setattr(sm.time, "sleep", lambda s: recorded.append(round(s, 1)))
    monkeypatch.setattr(sm.asyncio, "sleep", fake_async_sleep)
    return recorded


@pytest.mark.parametrize("use_async", [False, True])
def test_backoff_ends_when_the_minimum_gap_is_0(waits, use_async):
    s = sleeper(min_sleep=0)
    s.toomany_req()
    assert s.sleep == 1
    decay_fully(s)
    assert s.sleep == 0
    paced = asyncio.run(s.async_do_sleep()) if use_async else s.do_sleep()
    assert paced is False
    assert waits == []


def test_backoff_decays_to_the_minimum_gap():
    s = sleeper(min_sleep=0.3)
    s.sleep = 4
    decay_fully(s)
    assert s.sleep == 0.3


def test_backoff_above_the_floor_still_decays_gradually():
    s = sleeper(min_sleep=0)
    s.sleep = 3
    decay_fully(s, rounds=1)
    assert s.sleep == 2


def test_a_new_error_after_the_backoff_ended_starts_over():
    s = sleeper(min_sleep=0)
    s.toomany_req()
    decay_fully(s)
    s.toomany_req()
    assert s.sleep == 1


@pytest.mark.parametrize("use_async", [False, True])
def test_403_gap_applies_again_once_the_rate_limit_backoff_ended(waits, use_async):
    m = object.__new__(sm.sessionManager)
    m._rate_limit_sleeper = sleeper(min_sleep=0)
    m._forbidden_sleeper = sleeper(min_sleep=2)
    m._rate_limit_sleeper.toomany_req()
    decay_fully(m._rate_limit_sleeper)
    m._forbidden_sleeper._last_request_time = sm.arrow.now()
    if use_async:
        asyncio.run(m._async_wait_before_request())
    else:
        m._wait_before_request()
    assert len(waits) == 1 and 1.5 < waits[0] <= 2
