import subprocess
import logging
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.logs.utils.level import getNumber


def run(*args, log=None, **kwargs):
    log = log or logging.getLogger("shared")
    # ensure output is captured
    if not kwargs.get("capture_output",False):
        kwargs.update({"capture_output": True})
    # since we use capture_output, stderr and stdout may not be set
    kwargs.pop("stderr", None)
    kwargs.pop("stdout", None)

    # ensure input is str if using text=True
    if kwargs.get("text", False):
        if "input" in kwargs.keys():
            if isinstance(kwargs.get("input", None), (bytes, bytearray)):
                # bytes to str
                kwargs.update({"input": kwargs.get("input").decode("utf-8")})
            elif not isinstance(kwargs.get("input", None), (str)):
                # fallback for "any non str type"
                kwargs.update({"input": str(kwargs.get("input", ""), "utf-8")})
    
    t = subprocess.run(*args, **kwargs)
    level = (
        getNumber("DEBUG")
        if not of_env.getattr("LOG_SUBPROCESS")
        else of_env.getattr("LOG_SUBPROCESS_LEVEL")
    )
    if kwargs.get("text", False):
        if t.stdout:
            log.log(level, f"stdout: {t.stdout}")
        if t.stderr:
            log.log(level, f"stderr: {t.stderr}")
    else:
        if t.stdout:
            log.log(level, f"stdout: {t.stdout.decode()}")
        if t.stderr:
            log.log(level, f"stderr: {t.stderr.decode()}")
    return t
