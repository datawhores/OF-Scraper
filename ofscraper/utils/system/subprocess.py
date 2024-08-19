import subprocess
import logging
import ofscraper.utils.constants as constants
from ofscraper.utils.logs.utils.level import getLevel


def run(*args, log=None, **kwargs):
    log = log or logging.getLogger("shared")
    t = subprocess.run(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    level = (
        getLevel("DEBUG")
        if not constants.getattr("LOG_SUBPROCESS")
        else constants.getattr("LOG_SUBPROCESS_LEVEL")
    )
    if t.stdout:
        log.log(level, f"stdout: {t.stdout.decode()}")
    if t.stderr:
        log.log(level, f"stderr: {t.stderr.decode()}")
    return t
