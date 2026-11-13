import subprocess
import sys
import logging
import asyncio
import contextlib
import tempfile
import threading
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.context.exit as exit_context
from ofscraper.utils.system.process_tree import ProcessTree


def _format_subprocess_output(text_output):
    """
    Sanitizes subprocess output. Crucial for FFmpeg, which uses \r to overwrite
    terminal lines, causing massive garbled strings in standard log files.
    """
    if not text_output:
        return ""
    if isinstance(text_output, bytes):
        text_output = text_output.decode("utf-8", errors="ignore")
    # Replace carriage returns with proper newlines so log files can read it
    return text_output.replace("\r", "\n").strip()


def run(
    *args,
    log=None,
    stdout=None,
    stderr=None,
    capture_output=True,
    level=None,
    name=None,
    timeout=600,
    **kwargs,
):
    log = log or logging.getLogger("shared")
    cmd_args = list(args[0])

    if (
        cmd_args
        and isinstance(cmd_args[0], str)
        and cmd_args[0].lower().endswith(".py")
    ):
        cmd_args.insert(0, sys.executable)

    name = name or " ".join(cmd_args)

    level = (
        int(level)
        if level is not None
        else int(of_env.getattr("LOG_SUBPROCESS_LEVEL") or 0)
    )

    final_args = (cmd_args,) + args[1:]

    # If capture_output is True, subprocess.run handles the pipes automatically.
    if capture_output:
        kwargs["capture_output"] = True
    else:
        # If False, we respect whatever custom pipes were passed (or let them leak to terminal if None)
        kwargs["stdout"] = stdout
        kwargs["stderr"] = stderr
    # -----------------------

    try:
        t = subprocess.run(
            *final_args,
            timeout=timeout,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Subprocess {name} timed out after {timeout} seconds.")

    if level <= 0:
        return t

    if getattr(t, "stdout", None):
        log.log(level, f"{name} stdout:\n{_format_subprocess_output(t.stdout)}")
    if getattr(t, "stderr", None):
        log.log(level, f"{name} stderr:\n{_format_subprocess_output(t.stderr)}")

    return t


KILL_WAIT = 2  # seconds to wait for a killed process to be reaped


async def _kill(process, exited):
    """Kill the process if it still runs, and wait a bounded time for it."""
    if process.poll() is None:
        process.kill()
    await asyncio.wait([exited], timeout=KILL_WAIT)


def _write_input(file, data):
    file.write(data)
    file.seek(0)


async def _write_input_async(file, data):
    writing = asyncio.ensure_future(asyncio.to_thread(_write_input, file, data))
    try:
        await asyncio.shield(writing)
    except asyncio.CancelledError:
        # Closing the file waits for the thread still writing to it, which
        # would block the event loop: let the write finish first.
        await asyncio.wait([writing])
        raise


def _read_output(*files):
    contents = []
    for file in files:
        file.seek(0)
        contents.append(file.read())
    return contents


def _start(cmd_args, kwargs, tree):
    """Start the command and track it; return (process, untracked).

    Ctrl+C and SIGTERM are held from before the command starts until it is
    tracked, then delivered: otherwise an interrupt in between could leave it,
    and anything it starts, running untracked (on Windows, suspended outside
    any job). This is synchronous so nothing else runs while they are held.
    untracked is None, or the error that kept its programs from being tracked.
    """
    with exit_context.DelayedKeyboardInterrupt():
        process = subprocess.Popen(cmd_args, **tree.popen_kwargs(kwargs))
        try:
            untracked = tree.attach(process.pid)
        except BaseException:
            process.kill()
            process.wait()
            raise
    return process, untracked


def _exit_future(process):
    """Return a future that is done once the process has exited.

    A thread waits for it, as asyncio's own subprocess support does on
    Python 3.11, and reaps it.
    """
    loop = asyncio.get_running_loop()
    exited = loop.create_future()

    def wait():
        process.wait()
        try:
            loop.call_soon_threadsafe(_set_done, exited)
        except RuntimeError:
            pass  # the loop is closed: nothing waits for it any more

    threading.Thread(target=wait, name="async_run wait", daemon=True).start()
    return exited


def _set_done(future):
    if not future.done():
        future.set_result(None)


async def async_run(
    *args,
    log=None,
    level=None,
    name=None,
    timeout=600,
    capture_output=True,
    input=None,
    text=False,
    check=False,
    **kwargs,
):
    """
    Asynchronously executes a command without blocking the main event loop.

    The command's input and output go through temporary files, not pipes. A
    program the command starts in the background inherits them, and with
    pipes it kept them open, so we waited for that program long after the
    command had exited (#389, #391). A file has no reader to wait for: we wait
    for the command itself, then read everything it wrote.

    Programs the command started are stopped once it exits, is killed or is
    cancelled, so none are left running (see ProcessTree).
    """
    log = log or logging.getLogger("shared")
    cmd_args = list(args[0])

    if (
        cmd_args
        and isinstance(cmd_args[0], str)
        and cmd_args[0].lower().endswith(".py")
    ):
        cmd_args.insert(0, sys.executable)

    name = name or " ".join(cmd_args)

    if level is None:
        level = int(of_env.getattr("LOG_SUBPROCESS_LEVEL", "10"))

    if text and isinstance(input, str):
        input = input.encode("utf-8")

    with contextlib.ExitStack() as files:
        tree = files.enter_context(ProcessTree())
        if input is not None:
            kwargs["stdin"] = files.enter_context(tempfile.TemporaryFile())
            await _write_input_async(kwargs["stdin"], input)
        if capture_output:
            kwargs["stdout"] = files.enter_context(tempfile.TemporaryFile())
            kwargs["stderr"] = files.enter_context(tempfile.TemporaryFile())

        process, untracked = _start(cmd_args, kwargs, tree)
        if untracked:
            log.warning(
                f"Programs started by subprocess {name} can't be tracked, so "
                f"they won't be stopped when it exits: {untracked}"
            )
        exit_future = _exit_future(process)
        exited = False
        try:
            async with asyncio.timeout(timeout):
                # asyncio.wait doesn't cancel exit_future on a cancel or timeout
                await asyncio.wait([exit_future])
            exited = True
        except TimeoutError:
            await _kill(process, exit_future)
            raise TimeoutError(
                f"Subprocess {name} timed out after {timeout} seconds and was forcefully killed."
            ) from None
        except BaseException:
            # Cancelled (or failed): don't leave the command running.
            await _kill(process, exit_future)
            raise
        finally:
            # Don't leave anything it started running either.
            if await tree.running():
                if exited:
                    log.warning(
                        f"Subprocess {name} exited but left programs running; "
                        "stopping them."
                    )
                await tree.stop()

        if capture_output:
            stdout, stderr = await asyncio.to_thread(
                _read_output, kwargs["stdout"], kwargs["stderr"]
            )
        else:
            stdout = stderr = b""

    if text:
        stdout = stdout.decode("utf-8", errors="ignore")
        stderr = stderr.decode("utf-8", errors="ignore")

    if check and process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, cmd_args, output=stdout, stderr=stderr
        )

    class ProcessResult:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    t = ProcessResult(process.returncode, stdout, stderr)

    if level == 0:
        return t

    if t.stdout:
        log.log(level, f"{name} stdout:\n{_format_subprocess_output(t.stdout)}")
    if t.stderr:
        log.log(level, f"{name} stderr:\n{_format_subprocess_output(t.stderr)}")

    return t
