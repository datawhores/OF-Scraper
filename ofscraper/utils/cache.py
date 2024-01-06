from diskcache import Cache

import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths

cache = None


def get(*args, **kwargs):
    global cache
    if cache is None:
        cache = Cache(
            paths.getcachepath(), disk=config_.get_cache_mode(config_.read_config())
        )
    return cache.get(*args, **kwargs)


def set(*args, **kwargs):
    global cache
    if cache is None:
        cache = Cache(
            paths.getcachepath(), disk=config_.get_cache_mode(config_.read_config())
        )
    cache.set(*args, **kwargs)


def close(*args, **kwargs):
    global cache
    if cache is None:
        cache = Cache(
            paths.getcachepath(), disk=config_.get_cache_mode(config_.read_config())
        )
    cache.close(*args, **kwargs)
