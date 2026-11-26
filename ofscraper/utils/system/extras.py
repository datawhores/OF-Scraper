"""Install an optional extra the first time a feature needs it.

``--live`` on OnlyFans needs the ``live`` extra (Playwright) and a Chromium
browser; ``OFSC_DATABASE_URL`` needs psycopg, which is a dependency wherever it
has prebuilt wheels and the ``postgres`` extra elsewhere. Instead of stopping
with an install command, the first run asks to install them into the Python
running OF-Scraper, with pip, or with uv when that Python has no pip
(``uv pip install --python``). ``OFSC_INSTALL_EXTRAS=False`` turns this off.

It only asks at a terminal. The daemon, cron, services and ``sudo`` runs
get the install command to run themselves instead. The standalone download
can't add packages, so it never tries.
"""

import functools
import importlib
import importlib.util
import logging
import os
import shlex
import shutil
import site
import subprocess
import sys
import tempfile
import threading

log = logging.getLogger("shared")

# the same lists as [project.optional-dependencies] in pyproject.toml (test_extras checks it)
EXTRAS = {
    "postgres": ["psycopg[binary,pool]>=3.3.9"],
    "live": ["playwright>=1.40,<2"],
}
# a slow connection and Chromium's ~150 MB download
INSTALL_TIMEOUT = 1800

_lock = threading.Lock()


def _once(func):
    """lru_cache, with callers at the same time (threads asking for the
    PostgreSQL driver together) waiting for the one install instead of each
    starting their own."""
    cached = functools.lru_cache(maxsize=None)(func)

    @functools.wraps(func)
    def wrapper(*args):
        with _lock:
            return cached(*args)

    wrapper.cache_clear = cached.cache_clear
    return wrapper


def enabled() -> bool:
    import ofscraper.utils.of_env.of_env as of_env

    return bool(of_env.getattr("INSTALL_EXTRAS"))


# This Python, not importing modules from the working directory (-P): a pip.py
# there would otherwise run as pip. Not -E, which drops PYTHONPATH, so the pip
# this run found could be missing there. Not -I, which also hides the user
# site, where pip installs (and may itself be) when site-packages isn't
# writable.
PYTHON = [sys.executable, "-P"]


def _which_uv() -> str | None:
    """uv from PATH, skipping empty and relative entries, which mean the
    working directory (Windows PATHs often end with an empty one)."""
    for folder in os.get_exec_path():
        if not folder or not os.path.isabs(folder):
            continue
        found = shutil.which("uv", path=folder)
        if found:
            return found
    return None


def pip_command(requirements) -> list | None:
    """The command that installs ``requirements`` into this Python, or None."""
    if importlib.util.find_spec("pip"):
        return [*PYTHON, "-m", "pip", "install", *requirements]
    uv = _which_uv()
    if uv:
        # --no-config: no uv.toml or pyproject.toml can change the index
        return [uv, "pip", "install", "--no-config", "--python", sys.executable, *requirements]
    return None


def _shown(cmd) -> str:
    """``cmd`` as a line to paste into a shell."""
    if sys.platform != "win32":
        return shlex.join(cmd)
    # cmd.exe and PowerShell both take double quotes; <, >, [ and , need them
    return " ".join(
        f'"{arg}"' if not arg or any(c in arg for c in ' <>|&^,;=[]()\'"') else arg
        for arg in cmd
    )


def _under_sudo() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0 and "SUDO_USER" in os.environ


def _interactive() -> bool:
    """Someone at a terminal, and not the daemon."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
    except (ValueError, OSError):
        return False
    try:
        import ofscraper.utils.settings as settings

        if getattr(settings.get_args(), "daemon", None):
            return False
    except Exception as e:
        log.debug(f"couldn't tell whether this is the daemon: {e}")
        return False
    return True


def _may_run(cmd, what) -> bool:
    """Whether to run ``cmd``, which installs ``what``: asks at a terminal,
    otherwise logs the command to run instead."""
    shown = _shown(cmd)
    if _under_sudo():
        log.warning(f"Not installing {what} as root under sudo. To install, run: {shown}")
        return False
    if not _interactive():
        log.warning(
            f"Not installing {what}: there's no terminal to ask at (the daemon, "
            f"or no input). To install, run: {shown}"
        )
        return False
    try:
        answer = input(f"OF-Scraper needs {what}. Install them now with:\n  {shown}\n[y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _env() -> dict:
    """This environment, with ``OFSC_PROXY`` as the proxy for pip, uv and
    Playwright. Passed in the environment, not as --proxy, so its password
    isn't on a command line other users can list."""
    import ofscraper.utils.of_env.of_env as of_env

    env = dict(os.environ)
    proxy = of_env.getattr("PROXY")
    if proxy:
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            env[key] = proxy
    return env


def _run(cmd, what) -> bool:
    try:
        # an empty working directory: nothing there (uv.toml, pip.py) is read
        with tempfile.TemporaryDirectory(prefix="ofscraper-install-") as cwd:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=INSTALL_TIMEOUT,
                cwd=cwd,
                env=_env(),
            )
    except (OSError, subprocess.SubprocessError) as e:
        log.warning(f"Couldn't install {what}: {e}")
        return False
    if r.returncode != 0:
        said = "\n".join((r.stderr or r.stdout or "").strip().splitlines()[-5:])
        log.warning(f"Couldn't install {what}:\n{said}")
        return False
    log.debug(f"Installed {what}:\n{r.stdout}")
    return True


def _add_user_site():
    """Put the user site directory on sys.path. pip installs there (--user)
    when site-packages isn't writable, and Python only adds it at startup
    when it already exists."""
    if not site.ENABLE_USER_SITE:
        return
    user_site = site.getusersitepackages()
    if os.path.isdir(user_site) and user_site not in sys.path:
        site.addsitedir(user_site)


@_once
def install(extra: str) -> bool:
    """Install the ``extra`` packages, once per run. True when they were installed.

    A failure isn't retried until the next run: ``--live-watch`` asks again
    every interval.
    """
    if getattr(sys, "frozen", False) or not enabled():
        return False
    cmd = pip_command(EXTRAS[extra])
    if cmd is None:
        log.warning(f"Can't install the optional {extra!r} packages: this Python has neither pip nor uv")
        return False
    what = f"the optional {extra!r} packages"
    if not _may_run(cmd, what):
        return False
    log.info(f"Installing the optional {extra!r} packages; this happens once")
    ok = _run(cmd, what)
    # let this run import what was just installed
    _add_user_site()
    importlib.invalidate_caches()
    if ok:
        log.info(f"Installed the optional {extra!r} packages")
    return ok


@_once
def install_chromium() -> bool:
    """Download Playwright's Chromium, once per run. True when it worked."""
    if getattr(sys, "frozen", False) or not enabled():
        return False
    cmd = [*PYTHON, "-m", "playwright", "install", "chromium"]
    if not _may_run(cmd, "the Chromium browser for livestream recording (about 150 MB)"):
        return False
    log.info("Downloading the Chromium browser for livestream recording (about 150 MB); this happens once")
    ok = _run(cmd, "the Chromium browser")
    if ok:
        log.info("Chromium is installed")
    return ok
