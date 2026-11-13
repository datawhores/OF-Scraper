"""Shared stop request for fetching, download loops and the check-table worker."""

import asyncio
import logging
import signal
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

requested = threading.Event()
_lock = threading.RLock()
_transfers = {}
_fetches = set()
_fetch_workers = ContextVar("fetch_workers", default=None)


class DownloadsStopped(BaseException):
    """Unwind a stopped fetch or download after its cleanup."""


def clear():
    requested.clear()


def request():
    with _lock:
        if requested.is_set():
            return
        requested.set()
        for task in _transfers:
            task.get_loop().call_soon_threadsafe(_cancel, task)
        for task in _fetches:
            task.get_loop().call_soon_threadsafe(_cancel_fetch, task)


def _cancel(task):
    if not task.done():
        task.cancel()


def _cancel_fetch(task):
    # A synchronous check may already have started unwinding the fetch.
    # Do not deliver a late cancellation into its worker cleanup.
    with _lock:
        if task in _fetches:
            _cancel(task)


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


def create_fetch_task(coro):
    task = asyncio.create_task(coro)
    workers = _fetch_workers.get()
    if workers is not None:
        workers.append(task)
    return task


def fetching(func):
    """Cancel a whole fetch, including its page workers, before returning data.

    Nested API calls share their outer fetch's lifetime. Only that outer call
    converts cancellation to the scrape's stop exception, after workers unwind.
    """
    @wraps(func)
    async def inner(*args, **kwargs):
        if _fetch_workers.get() is not None:
            check()
            result = await func(*args, **kwargs)
            check()
            return result
        task = asyncio.current_task()
        workers = []
        token = _fetch_workers.set(workers)
        with _lock:
            _fetches.add(task)
        try:
            check()
            result = await func(*args, **kwargs)
            check()
            return result
        except asyncio.CancelledError:
            if requested.is_set():
                raise DownloadsStopped
            raise
        finally:
            with _lock:
                _fetches.discard(task)
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            _fetch_workers.reset(token)

    return inner


def started(media):
    check()
    media.download_started = True


def handle_interrupt(signum, frame):
    with _lock:
        fetch_active = bool(_fetches)
        active = fetch_active or any(m.download_started for m in _transfers.values())
    if requested.is_set() or not active:
        raise KeyboardInterrupt
    request()
    logging.getLogger("shared").warning(
        "Stopping the fetch. A second Ctrl+C quits." if fetch_active else
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
