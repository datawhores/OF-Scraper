import subprocess
import logging
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.logs.utils.level import getNumber


def run(*args, log=None, **kwargs):
    log = log or logging.getLogger("shared")
    t = subprocess.run(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    level = (
        getNumber("DEBUG")
        if not of_env.getattr("LOG_SUBPROCESS")
        else of_env.getattr("LOG_SUBPROCESS_LEVEL")
    )
    if t.stdout:
        log.log(level, f"stdout: {t.stdout.decode()}")
    if t.stderr:
        log.log(level, f"stderr: {t.stderr.decode()}")
    return t
