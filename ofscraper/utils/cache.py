from diskcache import Cache

import ofscraper.utils.args as args_
import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths

cache = None


def get(*args, **kwargs):
    if (
        args_.getargs().no_cache
        or config_.get_cache_mode(config_.read_config()) == "disabled"
    ):
        return kwargs.get("default")
    global cache
    if cache is None:
        cache = Cache(
            paths.getcachepath(), disk=config_.get_cache_mode(config_.read_config())
        )
    return cache.get(*args, **kwargs)


def set(*args, **kwargs):
    if (
        args_.getargs().no_cache
        or config_.get_cache_mode(config_.read_config()) == "disabled"
    ):
        return
    global cache
    if cache is None:
        cache = Cache(
            paths.getcachepath(), disk=config_.get_cache_mode(config_.read_config())
        )
    cache.set(*args, **kwargs)


def close(*args, **kwargs):
    if (
        args_.getargs().no_cache
        or config_.get_cache_mode(config_.read_config()) == "disabled"
    ):
        return None
    global cache
    if cache is None:
        cache = Cache(
            paths.getcachepath(), disk=config_.get_cache_mode(config_.read_config())
        )
    cache.close(*args, **kwargs)
