"""Cancelling a download must stop it, not start another attempt.

download_retry, the downloaders' retry loop, retried every exception except
KeyboardInterrupt and the out-of-space message. tenacity's attempt swallows
asyncio.CancelledError, so a Ctrl+C (or a cancelled task) during a transfer
started the download again (same cause as #155).
"""

import asyncio

from tenacity import stop_after_attempt, wait_none

from ofscraper.commands.scraper.actions.download.utils.retries import download_retry


def test_cancel_during_a_download_attempt_stops_it():
    attempts = []

    async def download():
        # the default retry condition is what's under test
        async for attempt in download_retry(stop=stop_after_attempt(3), wait=wait_none()):
            with attempt:
                attempts.append(1)
                await asyncio.sleep(10)

    async def run():
        task = asyncio.create_task(download())
        await asyncio.sleep(0.1)
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=3)
        stopped = task in done and task.cancelled()
        count = len(attempts)
        while not task.done():
            task.cancel()
            await asyncio.wait({task}, timeout=1)
        return stopped, count

    stopped, count = asyncio.run(run())
    assert stopped, f"the cancel was swallowed; {count} attempts were started"
    assert count == 1


def test_a_failed_download_attempt_is_still_retried():
    attempts = []

    async def download():
        async for attempt in download_retry(stop=stop_after_attempt(3), wait=wait_none()):
            with attempt:
                attempts.append(1)
                if len(attempts) < 3:
                    raise OSError("connection reset")

    asyncio.run(download())
    assert len(attempts) == 3
