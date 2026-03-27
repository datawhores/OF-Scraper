import subprocess
import sys
import logging
import asyncio
import ofscraper.utils.of_env.of_env as of_env


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
    Reads streams natively to avoid 'communicate()' closing stdin prematurely,
    ensuring stdout is ALWAYS perfectly captured.
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

    if capture_output:
        kwargs["stdout"] = asyncio.subprocess.PIPE
        kwargs["stderr"] = asyncio.subprocess.PIPE

    if input is not None:
        kwargs["stdin"] = asyncio.subprocess.PIPE
        if text and isinstance(input, str):
            input = input.encode("utf-8")

    process = await asyncio.create_subprocess_exec(*cmd_args, **kwargs)

    async def _read_stream(stream):
        if stream is None:
            return b""
        return await stream.read()

    async def _feed_stdin(stream, data):
        if stream is None or data is None:
            return
        try:
            stream.write(data)
            await stream.drain()
        except Exception:
            pass  # Silently swallow Broken Pipe errors if script ignores stdin
        finally:
            try:
                stream.close()
            except Exception:
                pass

    try:
        # 1. Start feeding stdin in the background
        if input is not None:
            asyncio.create_task(_feed_stdin(process.stdin, input))

        # 2. Read stdout and stderr concurrently
        out_task = asyncio.create_task(_read_stream(process.stdout))
        err_task = asyncio.create_task(_read_stream(process.stderr))

        # 3. Wait for the process to exit, bounded by timeout
        await asyncio.wait_for(process.wait(), timeout=timeout)

        # 4. Gather the exact output
        stdout = await out_task
        stderr = await err_task

    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(
            f"Subprocess {name} timed out after {timeout} seconds and was forcefully killed."
        )

    if text:
        if stdout is not None:
            stdout = stdout.decode("utf-8", errors="ignore")
        if stderr is not None:
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

    return t
