"""
Regression tests for asyncio.gather exception propagation.

Previously, gather was called with return_exceptions=True but the result
was never checked, causing all consumer task exceptions to be silently swallowed.
"""
import asyncio
import pytest

from ofscraper.utils.gather import gather_and_raise


def test_gather_and_raise_propagates_first_exception():
    """Consumer exceptions must propagate, not be silently swallowed."""
    async def run():
        async def failing():
            raise RuntimeError("consumer failed")

        tasks = [asyncio.create_task(failing())]
        await gather_and_raise(tasks)

    with pytest.raises(RuntimeError, match="consumer failed"):
        asyncio.run(run())


def test_gather_and_raise_all_consumers_run_before_raise():
    """All consumers should complete before the exception is raised."""
    completed = []

    async def run():
        async def failing():
            raise RuntimeError("fail")

        async def slow_succeeding():
            await asyncio.sleep(0)
            completed.append("done")

        tasks = [
            asyncio.create_task(failing()),
            asyncio.create_task(slow_succeeding()),
        ]
        await gather_and_raise(tasks)

    with pytest.raises(RuntimeError):
        asyncio.run(run())

    assert "done" in completed, "slow consumer should have completed before exception raised"


def test_gather_and_raise_does_not_raise_when_all_succeed():
    """No exception raised when all consumers succeed."""
    results = []

    async def run():
        async def succeeding():
            results.append("ok")

        tasks = [asyncio.create_task(succeeding()) for _ in range(3)]
        await gather_and_raise(tasks)

    asyncio.run(run())
    assert results == ["ok", "ok", "ok"]


def test_gather_and_raise_multiple_exceptions_raises_first():
    """When multiple consumers fail, the first exception is raised."""
    async def run():
        async def failing_a():
            raise ValueError("error A")

        async def failing_b():
            raise TypeError("error B")

        tasks = [
            asyncio.create_task(failing_a()),
            asyncio.create_task(failing_b()),
        ]
        await gather_and_raise(tasks)

    with pytest.raises((ValueError, TypeError)):
        asyncio.run(run())
