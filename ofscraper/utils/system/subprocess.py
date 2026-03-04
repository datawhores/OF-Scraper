import subprocess
import sys
import logging
import asyncio
import ofscraper.utils.of_env.of_env as of_env


def run(
    *args,
    log=None,
    stdout=None,
    stderr=None,
    capture_output=None,
    level=None,
    name=None,
    timeout=600, 
    **kwargs,
):
    """
    Executes a command, automatically using the current Python interpreter
    for .py files.
    """
    log = log or logging.getLogger("shared")

    cmd_args = list(args[0])

    if (cmd_args and isinstance(cmd_args[0], str) and cmd_args[0].lower().endswith(".py")):
        cmd_args.insert(0, sys.executable)

    name = name or " ".join(cmd_args)

    if level is None:
        level = int(of_env.getattr("LOG_SUBPROCESS_LEVEL", "0"))

    final_args = (cmd_args,) + args[1:]

    stdout = stdout if stdout else subprocess.PIPE
    stderr = stderr if stderr else subprocess.PIPE
    if capture_output:
        stdout = None  
        stderr = None

    try:
        t = subprocess.run(
            *final_args,
            stdout=stdout,
            stderr=stderr,
            capture_output=capture_output,
            timeout=timeout,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Subprocess {name} timed out after {timeout} seconds.")

    if level == 0:
        return t

    if t.stdout:
        output = t.stdout.decode(errors="ignore") if isinstance(t.stdout, bytes) else t.stdout
        log.log(level, f"{name} stdout: {output.strip()}")
    if t.stderr:
        error = t.stderr.decode(errors="ignore") if isinstance(t.stderr, bytes) else t.stderr
        log.log(level, f"{name} stderr: {error.strip()}")

    return t


async def async_run(
    *args,
    log=None,
    level=None,
    name=None,
    timeout=600, 
    capture_output=False,
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

    if (cmd_args and isinstance(cmd_args[0], str) and cmd_args[0].lower().endswith(".py")):
        cmd_args.insert(0, sys.executable)

    name = name or " ".join(cmd_args)

    if level is None:
        level = int(of_env.getattr("LOG_SUBPROCESS_LEVEL", "0"))

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
            pass # Silently swallow Broken Pipe errors if script ignores stdin
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
        raise TimeoutError(f"Subprocess {name} timed out after {timeout} seconds and was forcefully killed.")

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
        output_str = t.stdout if isinstance(t.stdout, str) else t.stdout.decode(errors="ignore")
        log.log(level, f"{name} stdout: {output_str.strip()}")
    if t.stderr:
        error_str = t.stderr if isinstance(t.stderr, str) else t.stderr.decode(errors="ignore")
        log.log(level, f"{name} stderr: {error_str.strip()}")

    return t