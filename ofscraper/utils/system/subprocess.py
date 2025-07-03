import sys
import subprocess
import logging
import ofscraper.utils.of_env.of_env as of_env




def run(
    *args, log=None, quiet=None, stdout=None, stderr=None, capture_output=None, **kwargs
):
    """
    Executes a command, automatically using the current Python interpreter
    for .py files.
    """
    log = log or logging.getLogger("shared")

    # The command and its arguments are in the first element of the 'args' tuple
    cmd_args = list(args[0])

    # Check if the command is a Python script
    if cmd_args and isinstance(cmd_args[0], str) and cmd_args[0].lower().endswith(".py"):
        # Prepend the path to the current Python executable.
        # This ensures the script runs with the same interpreter.
        cmd_args.insert(0, sys.executable)

    # Reassemble the arguments for subprocess.run
    final_args = (cmd_args,) + args[1:]

    # Set up standard streams
    quiet = quiet
    stdout = stdout if stdout else subprocess.PIPE
    stderr = stderr if stderr else subprocess.PIPE
    if capture_output:
        stdout = None  # Let subprocess.run handle piping when capturing
        stderr = None
        quiet = True

    # Execute the command
    t = subprocess.run(
        *final_args, stdout=stdout, stderr=stderr, capture_output=capture_output, **kwargs
    )

    # Optional logging
    if quiet or not of_env.getattr("LOG_SUBPROCESS"):
        return t

    if t.stdout:
        # Decode stdout if it's in bytes
        output = t.stdout.decode() if isinstance(t.stdout, bytes) else t.stdout
        log.log(100, f"stdout: {output}")
    if t.stderr:
        # Decode stderr if it's in bytes
        error = t.stderr.decode() if isinstance(t.stderr, bytes) else t.stderr
        log.log(100, f"stderr: {error}")

    return t
