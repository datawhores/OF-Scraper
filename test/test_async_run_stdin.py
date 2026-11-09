"""async_run keeps its stdin/stdout/stderr tasks and leaves none running (#381)."""

import asyncio
import sys

import pytest

from ofscraper.utils.system.subprocess import async_run


def _pending_tasks():
    current = asyncio.current_task()
    return [t for t in asyncio.all_tasks() if t is not current and not t.done()]


@pytest.fixture
def slow_stdin(monkeypatch):
    """Make writing to the child's stdin take `delay` seconds before it drains.

    This holds the stdin task open after the child has exited, the window in
    which an unreferenced task could be lost or left running.
    """
    state = {"delay": 0.0, "finished": 0}
    real_exec = asyncio.create_subprocess_exec

    async def fake_exec(*args, **kwargs):
        process = await real_exec(*args, **kwargs)
        if process.stdin is not None:
            real_drain = process.stdin.drain

            async def drain():
                await asyncio.sleep(state["delay"])
                try:
                    await real_drain()
                finally:
                    # Counted even on a broken pipe (child exited), which
                    # async_run swallows.
                    state["finished"] += 1

            process.stdin.drain = drain
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return state


def test_script_reading_all_stdin_gets_full_input(slow_stdin):
    slow_stdin["delay"] = 0.2
    data = b"x" * 100_000
    script = "import sys; print(len(sys.stdin.buffer.read()))"

    async def main():
        result = await async_run(
            [sys.executable, "-c", script], input=data, level=0, timeout=60
        )
        return result, _pending_tasks()

    result, pending = asyncio.run(main())
    assert result.returncode == 0
    assert int(result.stdout) == len(data)
    assert pending == []


def test_stdin_task_is_awaited_when_script_ignores_input(slow_stdin):
    slow_stdin["delay"] = 1.0
    script = "print('ok')"

    async def main():
        result = await async_run(
            [sys.executable, "-c", script], input=b"data", level=0, timeout=60
        )
        return result, _pending_tasks()

    result, pending = asyncio.run(main())
    assert result.returncode == 0
    assert result.stdout.strip() == b"ok"
    # The stdin task ran to the end before async_run returned.
    assert slow_stdin["finished"] == 1
    assert pending == []


def test_timeout_kills_and_leaves_no_task(slow_stdin):
    slow_stdin["delay"] = 30.0
    script = "import time; time.sleep(60)"

    async def main():
        with pytest.raises(TimeoutError, match="forcefully killed"):
            await async_run(
                [sys.executable, "-c", script], input=b"data", level=0, timeout=1
            )
        return _pending_tasks()

    assert asyncio.run(main()) == []
