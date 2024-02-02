from diskcache import Cache

import ofscraper.utils.config.data as data
import ofscraper.utils.logs.close as close_log
import ofscraper.utils.manager as manager
import ofscraper.utils.paths.common as common_paths


def shutdown():
    close_log.gracefulClose()
    manager.shutdown()


def forcedShutDown():
    close_log.forcedClose()
    manager.shutdown()


def closeCache():
    try:
        cache = Cache(
            common_paths.getcachepath(),
            disk=data.get_cache_mode(),
        )
        cache.close()
    except Exception as E:
        raise E
