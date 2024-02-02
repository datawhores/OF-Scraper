from diskcache import Cache

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.paths.common as common_paths

cache = None


def get(*args, **kwargs):
    if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
        return kwargs.get("default")
    global cache
    if cache is None:
        cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
    return cache.get(*args, **kwargs)


def set(*args, **kwargs):
    if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
        return
    global cache
    if cache is None:
        cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
    cache.set(*args, **kwargs)


def close(*args, **kwargs):
    if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
        return None
    global cache
    if cache is None:
        cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
    cache.close(*args, **kwargs)


def touch(*args, **kwargs):
    if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
        return None
    global cache
    if cache is None:
        cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
    cache.touch(*args, **kwargs)
