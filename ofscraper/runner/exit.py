from diskcache import Cache

import ofscraper.utils.config.data as data
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.manager as manager
import ofscraper.utils.paths.common as common_paths


def shutdown():
    logger.gracefulClose()
    manager.shutdown()


def forcedShutDown():
    logger.forcedClose()
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
