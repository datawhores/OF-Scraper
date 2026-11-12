"""Shared stop request for download loops and the check-table worker."""

import asyncio
import logging
import signal
import threading
from contextlib import contextmanager

requested = threading.Event()
_lock = threading.RLock()
_transfers = {}


class DownloadsStopped(BaseException):
    """Unwind the scrape after its download stats have been recorded."""


def clear():
    requested.clear()


def request():
    with _lock:
        if requested.is_set():
            return
        requested.set()
        for task in _transfers:
            task.get_loop().call_soon_threadsafe(_cancel, task)


def _cancel(task):
    if not task.done():
        task.cancel()


def check():
    if requested.is_set():
        raise asyncio.CancelledError


@contextmanager
def transfer(media):
    task = asyncio.current_task()
    media.download_started = False
    with _lock:
        _transfers[task] = media
        if requested.is_set():
            task.get_loop().call_soon(_cancel, task)
    try:
        check()
        yield
    finally:
        with _lock:
            _transfers.pop(task, None)


def started(media):
    check()
    media.download_started = True


def handle_interrupt(signum, frame):
    with _lock:
        active = any(m.download_started for m in _transfers.values())
    if requested.is_set() or not active:
        raise KeyboardInterrupt
    request()
    logging.getLogger("shared").warning(
        "Stopping downloads; Part files are kept for Resume. A second Ctrl+C quits."
    )


@contextmanager
def interrupt_handler():
    clear()
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGINT, handle_interrupt)
    try:
        yield
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)
