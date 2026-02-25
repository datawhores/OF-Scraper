# main/close/exit.py

import time
import ofscraper.utils.logs.close as close_log
import ofscraper.utils.manager as manager
import ofscraper.utils.cache as cache
import ofscraper.commands.scraper.actions.utils.globals as common_globals # Added

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
    if hasattr(common_globals, "thread") and common_globals.thread:
        common_globals.thread.shutdown(wait=True)
        common_globals.thread = None

def closeCache():
    try:
        cache.close()
    except Exception as E:
        raise E