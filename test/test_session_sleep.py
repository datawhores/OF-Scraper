import asyncio
import threading

import pytest

import ofscraper.utils.context.run_async as run_async
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


@pytest.mark.parametrize("contended", [True, False])
def test_threads_that_ended_do_not_keep_their_locks(contended):
    # @run gives each thread its own loop and never closes it. A lock that
    # was waited on holds its loop, so one lock and loop per thread used to
    # stay for the whole run
    sleeper = make_sleeper()
    loops = []  # closed at the end: an unclosed loop warns when collected

    @run_async.run
    async def work():
        loops.append(asyncio.get_running_loop())
        if contended:
            await asyncio.gather(sleeper.async_do_sleep(), sleeper.async_do_sleep())
        else:
            await sleeper.async_do_sleep()

    async def later():
        await sleeper.async_do_sleep()
        return len(sleeper._alocks)

    try:
        for _ in range(5):
            t = threading.Thread(target=work)
            t.start()
            t.join()
        assert len({id(x) for x in loops}) == 5  # a loop per thread, none closed
        # each thread's lock went when the next loop asked for one
        assert len(sleeper._alocks) <= 1
        assert asyncio.run(later()) == 1  # only the running loop's lock
    finally:
        for loop in loops:
            loop.close()


def test_toomany_req_works_across_event_loops():
    sleeper = make_sleeper()
    contend(sleeper, "async_toomany_req")
    contend(sleeper, "async_toomany_req")
