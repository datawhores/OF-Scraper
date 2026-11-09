"""async_run keeps its stdin/stdout/stderr tasks and leaves none running (#381)."""

import asyncio
import os
import signal
import sys
import time

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


@pytest.fixture
def spawned(monkeypatch):
    """Record every process async_run starts."""
    processes = []
    real_exec = asyncio.create_subprocess_exec

    async def fake_exec(*args, **kwargs):
        process = await real_exec(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return processes


async def _start_sleeping_script(spawned, **kwargs):
    script = "import time; time.sleep(60)"
    task = asyncio.create_task(
        async_run([sys.executable, "-c", script], level=0, timeout=60, **kwargs)
    )
    while not spawned:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.2)
    return task, spawned[0]


@pytest.mark.parametrize("input", [None, b"data"])
def test_cancel_kills_running_script(spawned, input):
    async def main():
        task, process = await _start_sleeping_script(spawned, input=input)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Killed and waited for before the cancel reached the caller.
        returncode, pending = process.returncode, _pending_tasks()
        await asyncio.sleep(0.2)  # let the pipe transports close
        return returncode, pending

    returncode, pending = asyncio.run(main())
    assert returncode is not None
    assert returncode != 0
    assert pending == []


def test_second_cancel_during_cleanup_still_raises(spawned):
    async def main():
        task, process = await _start_sleeping_script(spawned)
        task.cancel()
        for _ in range(3):  # let async_run reach its cleanup
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(process.wait(), timeout=10)
        await asyncio.sleep(0.2)  # let the pipe transports close
        return process, _pending_tasks()

    process, pending = asyncio.run(main())
    assert process.returncode is not None
    assert process.returncode != 0
    assert pending == []


def test_timeout_still_kills_script(spawned):
    async def main():
        with pytest.raises(TimeoutError, match="forcefully killed"):
            await async_run(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                level=0,
                timeout=1,
            )
        return spawned[0], _pending_tasks()

    process, pending = asyncio.run(main())
    assert process.returncode is not None
    assert pending == []


def test_normal_run_unchanged(spawned):
    result = asyncio.run(
        async_run([sys.executable, "-c", "print('ok')"], level=0, text=True)
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
    assert spawned[0].returncode == 0


# A script that starts a background program, which inherits the script's
# stdout/stderr and so keeps those pipes open after the script is killed (#389).
BACKGROUND_SLEEP = 20
PROMPT = 8  # well under BACKGROUND_SLEEP


@pytest.fixture
def background_script(tmp_path):
    pid_file = tmp_path / "background.pid"
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        f"'import time; time.sleep({BACKGROUND_SLEEP})'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    yield [sys.executable, "-c", script], pid_file
    # Don't leave the background program running after the test.
    if pid_file.exists():
        try:
            os.kill(int(pid_file.read_text()), signal.SIGTERM)
        except OSError:
            pass


async def _wait_for_file(path):
    for _ in range(200):
        if path.exists() and path.read_text():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("background program did not start")


def test_timeout_does_not_wait_for_background_program(background_script):
    cmd, pid_file = background_script

    async def main():
        start = time.monotonic()
        with pytest.raises(TimeoutError, match="forcefully killed"):
            await async_run(cmd, level=0, timeout=3)
        elapsed = time.monotonic() - start
        assert pid_file.exists()
        return elapsed, _pending_tasks()

    elapsed, pending = asyncio.run(main())
    assert elapsed < PROMPT
    assert pending == []


def test_cancel_does_not_wait_for_background_program(background_script):
    cmd, pid_file = background_script

    async def main():
        task = asyncio.create_task(async_run(cmd, level=0, timeout=60))
        await _wait_for_file(pid_file)
        start = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return time.monotonic() - start, _pending_tasks()

    elapsed, pending = asyncio.run(main())
    assert elapsed < PROMPT
    assert pending == []


def test_normal_run_captures_full_output():
    script = (
        "import sys\n"
        "sys.stdout.write('o' * 1_000_000)\n"
        "sys.stderr.write('e' * 500_000)\n"
    )
    result = asyncio.run(
        async_run([sys.executable, "-c", script], level=0, timeout=60)
    )
    assert result.returncode == 0
    assert result.stdout == b"o" * 1_000_000
    assert result.stderr == b"e" * 500_000
