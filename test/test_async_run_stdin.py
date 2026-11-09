"""async_run: input, output, timeouts and cancels, and scripts that start a
program in the background (#381, #387, #389, #391): those programs are
stopped once the script stops."""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time

import psutil
import pytest

import ofscraper.utils.system.process_tree as process_tree
import ofscraper.utils.system.subprocess as subprocess_module
from ofscraper.utils.system.subprocess import async_run


def _pending_tasks():
    current = asyncio.current_task()
    return [t for t in asyncio.all_tasks() if t is not current and not t.done()]


# More than a pipe buffer holds, on Windows and Linux.
BIG_INPUT = b"x" * 1_000_000


def test_script_reading_all_stdin_gets_full_input():
    script = "import sys; print(len(sys.stdin.buffer.read()))"

    async def main():
        result = await async_run(
            [sys.executable, "-c", script], input=BIG_INPUT, level=0, timeout=60
        )
        return result, _pending_tasks()

    result, pending = asyncio.run(main())
    assert result.returncode == 0
    assert int(result.stdout) == len(BIG_INPUT)
    assert pending == []


def test_script_ignoring_input_returns():
    async def main():
        result = await async_run(
            [sys.executable, "-c", "print('ok')"],
            input=BIG_INPUT,
            level=0,
            timeout=60,
        )
        return result, _pending_tasks()

    result, pending = asyncio.run(main())
    assert result.returncode == 0
    assert result.stdout.strip() == b"ok"
    assert pending == []


def test_text_input_and_output():
    script = "import sys; print(sys.stdin.read().upper())"
    result = asyncio.run(
        async_run(
            [sys.executable, "-c", script], input="café", text=True, level=0
        )
    )
    assert result.stdout.strip() == "CAFÉ"
    assert result.stderr == ""


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
        return process.returncode, _pending_tasks()

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
        return process, _pending_tasks()

    process, pending = asyncio.run(main())
    assert process.returncode is not None
    assert process.returncode != 0
    assert pending == []


@pytest.mark.parametrize("input", [None, b"data"])
def test_timeout_kills_script(spawned, input):
    async def main():
        with pytest.raises(TimeoutError, match="forcefully killed"):
            await async_run(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                input=input,
                level=0,
                timeout=1,
            )
        return spawned[0], _pending_tasks()

    process, pending = asyncio.run(main())
    assert process.returncode is not None
    assert pending == []


def test_no_timeout():
    """timeout=None means no time limit, as with asyncio.wait_for."""
    result = asyncio.run(
        async_run([sys.executable, "-c", "print('ok')"], level=0, timeout=None)
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b"ok"


def test_exit_is_not_polled(monkeypatch):
    """Waiting for the script schedules a fixed number of timers, not one
    every few milliseconds for as long as it runs."""
    scheduled = []

    async def main():
        loop = asyncio.get_running_loop()
        real_call_at = loop.call_at

        def call_at(when, callback, *args, **kwargs):
            scheduled.append(callback)
            return real_call_at(when, callback, *args, **kwargs)

        monkeypatch.setattr(loop, "call_at", call_at)
        return await async_run(
            [sys.executable, "-c", "import time; time.sleep(1.5)"],
            level=0,
            timeout=60,
        )

    result = asyncio.run(main())
    assert result.returncode == 0
    assert len(scheduled) < 5


def test_normal_run_unchanged(spawned):
    result = asyncio.run(
        async_run([sys.executable, "-c", "print('ok')"], level=0, text=True)
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"
    assert spawned[0].returncode == 0


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


def test_check_raises_with_output():
    script = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(4)"
    with pytest.raises(subprocess.CalledProcessError) as error:
        asyncio.run(
            async_run([sys.executable, "-c", script], level=0, check=True)
        )
    assert error.value.returncode == 4
    assert error.value.output.strip() == b"out"
    assert error.value.stderr.strip() == b"err"


def test_without_capture_output():
    result = asyncio.run(
        async_run(
            [sys.executable, "-c", "pass"], level=0, capture_output=False
        )
    )
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr == b""


# A program the script starts in the background inherits the script's stdin,
# stdout and stderr. It used to keep those pipes open, and async_run waited
# for it (#389, #391).
BACKGROUND_SLEEP = 20
PROMPT = 8  # well under BACKGROUND_SLEEP


def _kill_background(pid_file):
    if pid_file.exists() and pid_file.read_text():
        try:
            os.kill(int(pid_file.read_text()), signal.SIGTERM)
        except OSError:
            pass


@pytest.fixture
def background_script(tmp_path):
    """A script that starts a background program, then runs for a minute."""
    pid_file = tmp_path / "background.pid"
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        f"'import time; time.sleep({BACKGROUND_SLEEP})'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    yield [sys.executable, "-c", script], pid_file
    _kill_background(pid_file)


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


@pytest.fixture
def exiting_background_script(tmp_path):
    """A script that writes `size` bytes to stdout, starts a background
    program, and exits with `returncode` without reading its input."""
    pid_file = tmp_path / "background.pid"

    def make(returncode=0, size=0):
        script = (
            "import subprocess, sys\n"
            f"sys.stdout.write('o' * {size})\n"
            "print('script output')\n"
            "print('script error', file=sys.stderr)\n"
            "sys.stdout.flush()\n"
            "child = subprocess.Popen([sys.executable, '-c', "
            f"'import time; time.sleep({BACKGROUND_SLEEP})'])\n"
            f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
            f"sys.exit({returncode})\n"
        )
        return [sys.executable, "-c", script]

    yield make
    _kill_background(pid_file)


def test_script_exit_returns_despite_background_program(
    exiting_background_script,
):
    async def main():
        start = time.monotonic()
        result = await async_run(
            exiting_background_script(3), level=0, timeout=60
        )
        return result, time.monotonic() - start, _pending_tasks()

    result, elapsed, pending = asyncio.run(main())
    assert elapsed < PROMPT
    assert result.returncode == 3
    assert result.stdout.strip() == b"script output"
    assert result.stderr.strip() == b"script error"
    assert pending == []


def test_no_wait_after_script_exit(exiting_background_script):
    """Once the script exits, its result is used at once: there is nothing
    to wait for, even with a background program holding its output."""

    async def timed(cmd):
        start = time.monotonic()
        await async_run(cmd, level=0, timeout=60)
        return time.monotonic() - start

    async def main():
        plain = await timed([sys.executable, "-c", "import subprocess"])
        background = await timed(exiting_background_script())
        return background - plain

    # Starting the background program takes a few tens of milliseconds;
    # waiting for the output to close took seconds.
    assert asyncio.run(main()) < 1


def test_script_exit_check_raises_despite_background_program(
    exiting_background_script,
):
    async def main():
        start = time.monotonic()
        with pytest.raises(subprocess.CalledProcessError) as error:
            await async_run(
                exiting_background_script(2), level=0, timeout=60, check=True
            )
        return error.value, time.monotonic() - start

    error, elapsed = asyncio.run(main())
    assert elapsed < PROMPT
    assert error.returncode == 2
    assert error.output.strip() == b"script output"


def test_background_program_does_not_cut_off_output(exiting_background_script):
    """Everything the script wrote before it exited is returned."""
    result = asyncio.run(
        async_run(
            exiting_background_script(size=1_000_000), level=0, timeout=60
        )
    )
    assert result.stdout == b"o" * 1_000_000 + b"script output" + os.linesep.encode()


def test_unread_input_does_not_hold_up_return(exiting_background_script):
    """The script exits without reading its input, and the background program
    holds stdin; the call still returns promptly."""

    async def main():
        start = time.monotonic()
        result = await async_run(
            exiting_background_script(), level=0, timeout=60, input=BIG_INPUT
        )
        return result, time.monotonic() - start, _pending_tasks()

    result, elapsed, pending = asyncio.run(main())
    assert elapsed < PROMPT
    assert result.returncode == 0
    assert result.stdout.strip() == b"script output"
    assert pending == []


def test_kill_wait_is_bounded(monkeypatch):
    """A killed process that is never reaped doesn't hang async_run."""
    monkeypatch.setattr(subprocess_module, "KILL_WAIT", 0.5)

    class Unreaped:
        returncode = None

        def kill(self):
            pass

        async def wait(self):
            await asyncio.sleep(60)

    start = time.monotonic()
    asyncio.run(subprocess_module._kill(Unreaped()))
    assert time.monotonic() - start < 5


def _gone(pid):
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def _assert_gone(pid):
    # The program may take a moment to exit, or to be reaped by its new parent.
    for _ in range(100):
        if _gone(pid):
            return
        time.sleep(0.05)
    raise AssertionError(f"program {pid} is still running")


def test_background_program_stopped_after_script_exit(
    exiting_background_script, tmp_path, caplog
):
    log = logging.getLogger("test_async_run_tree")
    with caplog.at_level(logging.WARNING, logger=log.name):
        result = asyncio.run(
            async_run(exiting_background_script(), log=log, level=0, timeout=60)
        )
    assert result.stdout.strip() == b"script output"
    _assert_gone(int((tmp_path / "background.pid").read_text()))
    assert "left programs running" in caplog.text


def test_no_warning_without_leftover_programs(caplog):
    log = logging.getLogger("test_async_run_no_tree")
    with caplog.at_level(logging.WARNING, logger=log.name):
        asyncio.run(async_run([sys.executable, "-c", "pass"], log=log, level=0))
    assert caplog.text == ""


def test_background_program_stopped_on_timeout(background_script):
    cmd, pid_file = background_script
    with pytest.raises(TimeoutError):
        asyncio.run(async_run(cmd, level=0, timeout=2))
    _assert_gone(int(pid_file.read_text()))


def test_background_program_stopped_on_cancel(background_script):
    cmd, pid_file = background_script

    async def main():
        task = asyncio.create_task(async_run(cmd, level=0, timeout=60))
        await _wait_for_file(pid_file)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
    _assert_gone(int(pid_file.read_text()))


def _nested_script(pid_file, program):
    """A script that starts `program` in the background, which starts a
    second program; both pids go to pid_file. The script then exits."""
    inner = (
        "import subprocess, sys, time; "
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        f"open({str(pid_file)!r}, 'a').write(f' {{c.pid}}'); "
        f"{program}"
    )
    return [
        sys.executable,
        "-c",
        "import subprocess, sys, time\n"
        f"c = subprocess.Popen([sys.executable, '-c', {inner!r}])\n"
        f"open({str(pid_file)!r}, 'a').write(f' {{c.pid}}')\n"
        "while len(open(" + repr(str(pid_file)) + ").read().split()) < 2:\n"
        "    time.sleep(0.05)\n",
    ]


def test_programs_started_by_background_programs_are_stopped(tmp_path):
    pid_file = tmp_path / "pids"
    cmd = _nested_script(pid_file, "time.sleep(30)")
    asyncio.run(async_run(cmd, level=0, timeout=60))
    pids = [int(pid) for pid in pid_file.read_text().split()]
    assert len(pids) == 2
    for pid in pids:
        _assert_gone(pid)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_program_ignoring_sigterm_is_killed(tmp_path, monkeypatch):
    monkeypatch.setattr(process_tree, "STOP_WAIT", 0.5)
    pid_file = tmp_path / "pids"
    ignore = "import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    cmd = _nested_script(pid_file, ignore)
    start = time.monotonic()
    asyncio.run(async_run(cmd, level=0, timeout=60))
    assert time.monotonic() - start < 5
    for pid in pid_file.read_text().split():
        _assert_gone(int(pid))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_cancel_while_stopping_still_kills(tmp_path, monkeypatch, spawned):
    """A cancel during the wait after SIGTERM still sends SIGKILL."""
    monkeypatch.setattr(process_tree, "STOP_WAIT", 30)
    pid_file = tmp_path / "pids"
    ignore = "import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    cmd = _nested_script(pid_file, ignore)

    async def main():
        task = asyncio.create_task(async_run(cmd, level=0, timeout=60))
        while not spawned or spawned[0].returncode is None:
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.3)  # now waiting for the programs to exit
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
    for pid in pid_file.read_text().split():
        _assert_gone(int(pid))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_zombie_does_not_count_as_running():
    """A program that exited but wasn't reaped isn't waited for: in Docker,
    ofscraper is PID 1 and inherits orphans it never reaps."""
    child = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    try:
        while psutil.Process(child.pid).status() != psutil.STATUS_ZOMBIE:
            time.sleep(0.01)
        with process_tree.ProcessTree() as tree:
            tree.attach(child.pid)
            assert not asyncio.run(tree.running())
    finally:
        child.wait()


# Runs a command through the app's own entry wrapper (run_async.run), as a
# download does, and writes the pids of the script and its program.
CTRL_C_WRAPPER = """
import sys
sys.argv = sys.argv[:1]
import ofscraper.__main__  # noqa: F401  (import order, see AGENTS.md)
from ofscraper.utils.context import run_async
from ofscraper.utils.system.subprocess import async_run

pid_file = {pid_file!r}
script = (
    "import os, subprocess, sys, time\\n"
    "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\\n"
    f"open({{pid_file!r}}, 'w').write(f'{{{{os.getpid()}}}} {{{{c.pid}}}}')\\n"
    "time.sleep(30)\\n"
)

@run_async.run
async def main():
    await async_run([sys.executable, "-c", script], level=0, timeout=60)

main()
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_ctrl_c_stops_script_and_its_programs(tmp_path):
    """Ctrl+C leaves running tasks unfinished, so async_run's cleanup never
    runs; the script and its programs are killed when ofscraper exits."""
    pid_file = tmp_path / "pids"
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(CTRL_C_WRAPPER.format(pid_file=str(pid_file)))
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "PYTHONPATH": repo}
    # Its own session, like a terminal's foreground group: Ctrl+C signals it.
    app = subprocess.Popen(
        [sys.executable, str(wrapper)],
        env=env,
        start_new_session=True,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(200):
            if pid_file.exists() and len(pid_file.read_text().split()) == 2:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("script did not start")
        os.killpg(app.pid, signal.SIGINT)
        app.wait(timeout=30)
        for pid in pid_file.read_text().split():
            _assert_gone(int(pid))
    finally:
        if app.poll() is None:
            app.kill()
            app.wait()
        if pid_file.exists():
            for pid in pid_file.read_text().split():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except OSError:
                    pass


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_running_check_does_not_block_event_loop(monkeypatch):
    """The scan for live programs runs off the event loop: with many
    zombies it takes tens of milliseconds, repeated while stopping."""

    def slow_scan(pgid):
        time.sleep(0.5)
        return True

    monkeypatch.setattr(process_tree, "_live_member", slow_scan)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
    )

    async def main():
        ticks = 0

        async def tick():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        ticker = asyncio.create_task(tick())
        with process_tree.ProcessTree() as tree:
            tree.attach(child.pid)
            assert await tree.running()
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)
        return ticks

    try:
        assert asyncio.run(main()) >= 10
    finally:
        child.kill()
        child.wait()


def test_cancel_while_writing_input_lets_the_write_finish(monkeypatch):
    """Closing the input file while a thread still writes to it blocks the
    event loop (the write holds the file's lock), so a cancel waits for the
    write first."""
    closed_during_write = []
    real_write = subprocess_module._write_input

    def slow_write(file, data):
        time.sleep(0.5)
        closed_during_write.append(file.closed)
        if not file.closed:
            real_write(file, data)

    monkeypatch.setattr(subprocess_module, "_write_input", slow_write)

    async def main():
        task = asyncio.create_task(
            async_run([sys.executable, "-c", "pass"], input=b"data", level=0)
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return _pending_tasks()

    assert asyncio.run(main()) == []
    assert closed_during_write == [False]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_second_cancel_during_scan_still_stops_programs(
    background_script, monkeypatch
):
    """A second cancel while checking for leftover programs, before they
    are stopped, still leaves none running."""
    cmd, pid_file = background_script
    real_scan = process_tree._live_member

    def slow_scan(pgid):
        time.sleep(0.5)  # a scan with many zombies is slow
        return real_scan(pgid)

    monkeypatch.setattr(process_tree, "_live_member", slow_scan)

    async def main():
        task = asyncio.create_task(async_run(cmd, level=0, timeout=60))
        await _wait_for_file(pid_file)
        task.cancel()
        await asyncio.sleep(0.1)  # now scanning
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
    _assert_gone(int(pid_file.read_text()))


def test_caller_creationflags_are_kept(monkeypatch):
    monkeypatch.setattr(process_tree.sys, "platform", "win32")
    kwargs = process_tree.ProcessTree().popen_kwargs({"creationflags": 0x10})
    assert kwargs["creationflags"] == 0x10 | process_tree._CREATE_SUSPENDED


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="on Windows the script is suspended until it is tracked",
)
@pytest.mark.parametrize("cancels", [1, 2])
def test_cancel_while_starting_stops_script_and_its_programs(
    tmp_path, monkeypatch, cancels
):
    """A cancel while the script is starting, after it has started a
    program, still leaves neither running: the start is finished so the
    program can be tracked, then both are stopped."""
    pid_file = tmp_path / "pids"
    script = (
        "import os, subprocess, sys, time\n"
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open({str(pid_file)!r}, 'w').write(f'{{os.getpid()}} {{c.pid}}')\n"
        "time.sleep(30)\n"
    )
    real_exec = asyncio.create_subprocess_exec

    async def slow_start(*args, **kwargs):
        # Stretch the moment between the script starting and async_run
        # getting it back, so the cancel lands there.
        process = await real_exec(*args, **kwargs)
        await asyncio.sleep(1)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow_start)

    async def main():
        task = asyncio.create_task(
            async_run([sys.executable, "-c", script], level=0, timeout=60)
        )
        await _wait_for_file(pid_file)
        while len(pid_file.read_text().split()) < 2:
            await asyncio.sleep(0.01)
        for _ in range(cancels):
            task.cancel()
            await asyncio.sleep(0.05)
        with pytest.raises(asyncio.CancelledError):
            await task
        return _pending_tasks()

    try:
        assert asyncio.run(main()) == []
        for pid in pid_file.read_text().split():
            _assert_gone(int(pid))
    finally:
        if pid_file.exists():
            for pid in pid_file.read_text().split():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except OSError:
                    pass


def test_start_failure_is_raised(tmp_path):
    with pytest.raises(FileNotFoundError):
        asyncio.run(async_run([str(tmp_path / "missing")], level=0))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_no_signal_to_a_group_that_already_exited(monkeypatch):
    """If the programs exit between the check and the stop, the group isn't
    signalled again: its id could in theory belong to a new group by then."""
    child = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    child.wait()  # the group is gone
    sent = []
    real_signal = process_tree._signal_group

    def record(pgid, sig):
        sent.append(sig)
        return real_signal(pgid, sig)

    monkeypatch.setattr(process_tree, "_signal_group", record)
    with process_tree.ProcessTree() as tree:
        tree.attach(child.pid)
        asyncio.run(tree.stop())
    assert sent == [signal.SIGTERM]


def test_cancel_during_failed_start_logs_nothing(monkeypatch):
    """A cancel during a start that then fails raises CancelledError, and
    the start's error isn't reported to the event loop as unhandled."""

    async def failing_start(*args, **kwargs):
        await asyncio.sleep(0.5)
        raise FileNotFoundError("missing")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", failing_start)
    reported = []

    async def main():
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, context: reported.append(context)
        )
        task = asyncio.create_task(async_run(["missing"], level=0))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.1)  # let any report arrive
        return _pending_tasks()

    assert asyncio.run(main()) == []
    assert reported == []
