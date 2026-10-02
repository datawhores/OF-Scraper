import asyncio


async def gather_and_raise(tasks):
    """Await all tasks and re-raise the first exception, if any.

    Uses return_exceptions=True so all tasks run to completion before
    raising, rather than cancelling sibling tasks on first failure.
    """
    results = await asyncio.gather(*tasks, return_exceptions=True)
    exc = next((r for r in results if isinstance(r, BaseException)), None)
    if exc:
        raise exc
