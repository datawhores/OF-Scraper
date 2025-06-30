import subprocess
import logging
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.logs.utils.level import getNumber


def run(
    *args, log=None, quiet=None, stdout=None, stderr=None, capture_output=None, **kwargs
):
    log = log or logging.getLogger("shared")
    quiet = quiet
    stdout = stdout if stdout else subprocess.PIPE
    stderr = stderr if stderr else subprocess.PIPE
    if capture_output:
        stdout = None
        stderr = None
        quiet = True
    t = subprocess.run(
        *args, stdout=stdout, stderr=stderr, capture_output=capture_output, **kwargs
    )
    if quiet or not of_env.getattr("LOG_SUBPROCESS"):
        return t
    if t.stdout:
        log.log(100, f"path: stdout: {t.stdout.decode()}")
    if t.stderr:
        log.log(100, f"stderr: {t.stderr.decode()}")
    return t
