import subprocess
import sys
import logging
import ofscraper.utils.of_env.of_env as of_env


def run(
    *args,
    log=None,
    stdout=None,
    stderr=None,
    capture_output=None,
    level=None,
    name=None,
    **kwargs,
):
    """
    Executes a command, automatically using the current Python interpreter
    for .py files.
    """
    log = log or logging.getLogger("shared")

    # The command and its arguments are in the first element of the 'args' tuple
    cmd_args = list(args[0])

    # Check if the command is a Python script
    if (
        cmd_args
        and isinstance(cmd_args[0], str)
        and cmd_args[0].lower().endswith(".py")
    ):
        # Prepend the path to the current Python executable.
        cmd_args.insert(0, sys.executable)

    # Provide a default name for logging if not supplied
    name = name or " ".join(cmd_args)

    # Correctly initialize the log level
    if level is None:
        level = int(of_env.getattr("LOG_SUBPROCESS_LEVEL", "0"))

    # Reassemble the arguments for subprocess.run
    final_args = (cmd_args,) + args[1:]

    # Set up standard streams
    stdout = stdout if stdout else subprocess.PIPE
    stderr = stderr if stderr else subprocess.PIPE
    if capture_output:
        stdout = None  # Let subprocess.run handle piping when capturing
        stderr = None

    # Execute the command
    t = subprocess.run(
        *final_args,
        stdout=stdout,
        stderr=stderr,
        capture_output=capture_output,
        **kwargs,
    )

    # Conditional logging (level 0 means OFF)
    if level == 0:
        return t

    if t.stdout:
        # Decode stdout if it's in bytes
        output = (
            t.stdout.decode(errors="ignore")
            if isinstance(t.stdout, bytes)
            else t.stdout
        )
        # Correctly call the logger
        log.log(level, f"{name} stdout: {output.strip()}")
    if t.stderr:
        # Decode stderr if it's in bytes
        error = (
            t.stderr.decode(errors="ignore")
            if isinstance(t.stderr, bytes)
            else t.stderr
        )
        # Correctly call the logger
        log.log(level, f"{name} stderr: {error.strip()}")

    return t
