import time
import os
import logging

import psutil
import ofscraper.utils.logs.close as close_log
import ofscraper.utils.manager as manager
import ofscraper.utils.cache as cache

log = logging.getLogger("shared")


def shutdown():
    time.sleep(3)
    close_log.gracefulClose()
    manager.shutdown()
    closeCache()
    closeThreadExecutor()
    logResourceCleanup()


def forcedShutDown():
    time.sleep(3)
    manager.shutdown()
    closeCache()
    closeThreadExecutor()


def closeCache():
    try:
        cache.close()
    except Exception as E:
        raise E


def closeThreadExecutor():
    """Shutdown the global ThreadPoolExecutor to prevent resource leaks."""
    try:
        import ofscraper.commands.scraper.actions.utils.globals as common_globals
        if hasattr(common_globals, 'thread') and common_globals.thread:
            common_globals.thread.shutdown(wait=True)
            common_globals.thread = None
    except Exception as E:
        pass  # Silently ignore if executor is not initialized or already closed


def logResourceCleanup():
    """Log resource state at shutdown for leak detection."""
    try:
        process = psutil.Process(os.getpid())
        num_fds = len(process.open_files())
        num_threads = process.num_threads()

        log.trace(f"[RESOURCE] Shutdown verification | Open file descriptors: {num_fds} | Threads: {num_threads}")

        if num_fds > 50:
            log.warning(f"[RESOURCE] ⚠️ Possible file descriptor leak: {num_fds} files still open at shutdown")
            open_files = process.open_files()
            sample = [f.path for f in open_files[:10]]
            log.warning(f"[RESOURCE] Sample of open files: {sample}")
    except Exception:
        pass
