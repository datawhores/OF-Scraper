import time


import ofscraper.utils.logs.close as close_log
import ofscraper.utils.manager as manager
import ofscraper.utils.cache as cache


def shutdown():
    time.sleep(3)
    close_log.gracefulClose()
    manager.shutdown()
    closeCache()


def forcedShutDown():
    time.sleep(3)
    close_log.forcedClose()
    manager.shutdown()
    closeCache()


def closeCache():
    try:
        cache.close()
    except Exception as E:
        raise E
