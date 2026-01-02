import time


import ofscraper.utils.logs.close as close_log
import ofscraper.utils.manager as manager
import ofscraper.utils.cache as cache


def shutdown():
    time.sleep(3)
    close_log.gracefulClose()
    manager.shutdown()
    closeCache()
    closeThreadExecutor()


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
