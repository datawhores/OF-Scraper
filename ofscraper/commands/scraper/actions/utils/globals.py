"""The state shared by the downloads (and metadata updates) of a run.

It lives in a DownloadContext. The download managers take one when they're
made, and use their own; one made without a context uses the process's
current one, which main_globals() and set_up_contexvars() fill in at the
start of each run, as they filled in this module's names before.

The names this module had (common_globals.log, .sem, .photo_count, ...)
still read and write the current context, so code that hasn't moved to a
context of its own, and tests that patch those names, see the same values
as the managers that use it.
"""

import asyncio
import contextvars
import sys
import types
from concurrent.futures import ThreadPoolExecutor

import ofscraper.utils.console as console_
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.settings as settings

# the counters reset by init_run_state
_COUNTERS = (
    "total_bytes_downloaded",
    "total_bytes",
    "photo_count",
    "video_count",
    "audio_count",
    "skipped",
    "stopped",
    "forced_skipped",
)


class DownloadContext:
    """What the downloads of one run share: the counters shown in the
    progress bar and summary, the semaphore that limits how many files
    download at once, the thread pool for disk and cache work, the lock for
    total_bytes, the folders written to, the log, and the attempt counters
    (contextvars, so each download task has its own count).

    A new context has no pool, semaphore, locks or contextvars yet:
    init_contextvars() and init_run_state() make them, as
    set_up_contexvars() and main_globals() did for this module. The
    semaphore and lock bind to the event loop that first waits on them, as
    before."""

    def __init__(self):
        self.attempt = None
        self.attempt2 = None
        self.total_count = None
        self.total_count2 = None
        self.innerlog = None
        self.localDirSet = None
        self.log = None
        for name in _COUNTERS:
            setattr(self, name, 0)
        self.thread = None
        self.sem = None
        self.dirSet = None
        self.lock = None
        self.console = None
        self.fileHashes = None

    @classmethod
    def for_run(cls, download_sems, log=None, console=None):
        """A context ready for downloads: contextvars and run state made,
        with download_sems downloads at a time. log and console default to
        the shared ones."""
        ctx = cls()
        ctx.init_contextvars()
        ctx.init_run_state(download_sems, log=log, console=console)
        return ctx

    def init_run_state(self, download_sems=None, log=None, console=None):
        """Reset the counters and make the lock, pool, semaphore and folder
        sets for a run. download_sems defaults to the setting. They're made
        in the order main_globals() made them."""
        for name in _COUNTERS:
            setattr(self, name, 0)
        if download_sems is None:
            download_sems = settings.get_settings().download_sems
        self.thread = ThreadPoolExecutor(max_workers=download_sems * 2)
        self.sem = asyncio.Semaphore(download_sems)
        self.dirSet = set()
        self.lock = asyncio.Lock()
        self.console = console if console is not None else console_.get_shared_console()
        self.localDirSet = set()
        self.fileHashes = {}
        self.log = (
            log if log is not None else logger.get_shared_logger(name="ofscraper_download")
        )

    def init_contextvars(self):
        self.attempt = contextvars.ContextVar("attempt", default=0)
        self.attempt2 = contextvars.ContextVar("attempt2", default=0)
        self.total_count = contextvars.ContextVar("total", default=0)
        self.total_count2 = contextvars.ContextVar("total2", default=0)


# the process's context: made once and never replaced, so everything that
# holds it (a manager, this module's names) holds the same one. Each run
# resets it in place
_current = DownloadContext()

_NAMES = tuple(vars(_current))


def current():
    """The process's context, which main_globals() fills in for each run."""
    return _current


def main_globals():
    _current.init_run_state()


def mainProcessVariableInit():
    set_up_contexvars()
    main_globals()


def set_up_contexvars():
    _current.init_contextvars()


class _Module(types.ModuleType):
    """This module, with its old names reading and writing the current
    context."""


def _name_property(name):
    return property(
        lambda self: getattr(_current, name),
        lambda self, value: setattr(_current, name, value),
    )


for _name in _NAMES:
    setattr(_Module, _name, _name_property(_name))
del _name

sys.modules[__name__].__class__ = _Module
