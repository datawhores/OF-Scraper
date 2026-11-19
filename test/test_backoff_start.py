"""The first rate-limit error starts the backoff when a minimum gap is set.

With a minimum gap (0.5 s for API sessions) the sleep already equals it, so
a check for "no sleep yet" never fired: the first 429 left the sleep at the
gap, and 429s within the increase window changed nothing.
"""

import ofscraper.managers.sessionmanager.sessionmanager as sm


def sleeper(min_sleep, sleep=2.5):
    # the API session defaults
    return sm.SessionSleep(
        sleep=sleep,
        min_sleep=min_sleep,
        difmin=30,
        max_sleep=180,
        decay_threshold=120,
        decay_factor=1.5,
        increase_factor=2,
        error_name="test",
    )


def test_first_error_starts_at_the_starting_value():
    s = sleeper(min_sleep=0.5)
    s.toomany_req()
    assert s.sleep == 2.5


def test_errors_in_a_burst_keep_the_starting_value():
    s = sleeper(min_sleep=0.5)
    for _ in range(4):
        s.toomany_req()
    assert s.sleep == 2.5


def test_an_error_after_the_window_doubles_it():
    s = sleeper(min_sleep=0.5)
    s.toomany_req()
    # well past the 30 s window, never on its boundary
    s._last_raise = sm.arrow.now().shift(seconds=-60)
    s.toomany_req()
    assert s.sleep == 5


def test_an_error_after_decay_to_the_gap_starts_over():
    s = sleeper(min_sleep=0.5)
    s.sleep = 0.5
    s._last_date = sm.arrow.now().shift(seconds=-600)
    s.toomany_req()
    assert s.sleep == 2.5


def test_a_starting_value_at_or_below_the_gap_still_backs_off():
    # backoff mode needs a sleep above the gap
    s = sleeper(min_sleep=1, sleep=0.5)
    s.toomany_req()
    assert s.sleep > 1
