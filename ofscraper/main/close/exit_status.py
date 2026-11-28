"""Run-level exit codes for scripts and schedulers.

Kept free of imports from the rest of the app so any module can record an
outcome without introducing new coupling.
"""

from enum import IntEnum
import threading


class ExitCode(IntEnum):
    OK = 0
    ERROR = 1
    USAGE = 2
    AUTH = 3
    PARTIAL = 4
    UNAVAILABLE = 5
    CONFIG = 6
    INTERRUPTED = 130


OK = ExitCode.OK
ERROR = ExitCode.ERROR
USAGE = ExitCode.USAGE
AUTH = ExitCode.AUTH
PARTIAL = ExitCode.PARTIAL
UNAVAILABLE = ExitCode.UNAVAILABLE
CONFIG = ExitCode.CONFIG
INTERRUPTED = ExitCode.INTERRUPTED

# Ordered from least severe to most severe so the worst outcome wins.
# USAGE is recorded mid-run only for a -u name no creator has: any real
# run outcome beside it (partial, failed, login failed) wins.
_SEVERITY = {
    OK: 0,
    USAGE: 1,
    PARTIAL: 2,
    UNAVAILABLE: 3,
    AUTH: 4,
    CONFIG: 5,
    ERROR: 6,
    INTERRUPTED: 7,
}

_LABELS = {
    OK: "ok",
    PARTIAL: "partial",
    UNAVAILABLE: "site unavailable",
    AUTH: "login failed",
    CONFIG: "configuration error",
    ERROR: "unexpected error",
    USAGE: "usage error",
    INTERRUPTED: "interrupted",
}

_lock = threading.Lock()
_status = OK


def record(status: int) -> int:
    """Record an outcome, keeping the more severe one."""
    global _status
    incoming = ExitCode(status)
    with _lock:
        if _SEVERITY[incoming] > _SEVERITY[_status]:
            _status = incoming
        return int(_status)


def code() -> int:
    """Return the worst exit code recorded for the current run."""
    with _lock:
        return int(_status)


def reset() -> int:
    """Reset the recorded status to OK and return the previous code."""
    global _status
    with _lock:
        previous = int(_status)
        _status = OK
        return previous


def label(status: int = None) -> str:
    """Short human-readable name for a status code (default: current code)."""
    target = ExitCode(code() if status is None else status)
    return _LABELS[target]
