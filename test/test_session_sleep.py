import asyncio

from ofscraper.managers.sessionmanager.sessionmanager import SessionSleep


def make_sleeper():
    # A current sleep above min_sleep is backoff mode, so async_do_sleep awaits
    # while holding the async lock and a second caller has to wait on it
    sleeper = SessionSleep(
        sleep=0.02,
        min_sleep=0.01,
        difmin=0,
        max_sleep=0.05,
        decay_threshold=60,
        decay_factor=1.5,
        increase_factor=1.5,
        error_name="test",
    )
    sleeper.sleep = 0.02
    return sleeper


def contend(sleeper, second_method):
    async def run():
        await asyncio.gather(
            sleeper.async_do_sleep(), getattr(sleeper, second_method)()
        )

    asyncio.run(run())


def test_do_sleep_works_across_event_loops():
    # ofscraper runs async code in several loops (@run starts a new one per
    # call); a shared asyncio.Lock binds to the first loop that contends on it.
    sleeper = make_sleeper()
    contend(sleeper, "async_do_sleep")
    contend(sleeper, "async_do_sleep")


def test_toomany_req_works_across_event_loops():
    sleeper = make_sleeper()
    contend(sleeper, "async_toomany_req")
    contend(sleeper, "async_toomany_req")
