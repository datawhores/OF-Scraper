import time
import ofscraper.utils.logs.close as close_log
import ofscraper.utils.manager as manager
import ofscraper.utils.cache.cache as cache


def shutdown():
    time.sleep(3)
    close_log.gracefulClose()
    manager.shutdown()
    closeThreadExecutor()
    closeCache()


def forcedShutDown():
    time.sleep(3)
    manager.shutdown()
    closeThreadExecutor()
    closeCache()


def closeThreadExecutor():
    # MOVE THE IMPORT HERE
    # This prevents the circular dependency during startup
    try:
        import ofscraper.commands.scraper.actions.utils.globals as common_globals

        if hasattr(common_globals, "thread") and common_globals.thread:
            common_globals.thread.shutdown(wait=True)
            common_globals.thread = None
    except ImportError:
        pass


def closeCache():
    try:
        cache.close()
    except Exception:
        pass
