import threading

from diskcache import Cache

import ofscraper.utils.config.data as data
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings

cache = None
lock = threading.Lock()


def get(*args, **kwargs):
    global lock
    with lock:
        if settings.get_settings().cached_disabled:
            return kwargs.get("default")
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        return cache.get(*args, **kwargs)


def set(*args, auto_close=True, **kwargs):
    global lock
    with lock:
        if settings.get_settings().cached_disabled:
            return
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.set(*args, **kwargs)
    if auto_close:
        close()


def close(*args, **kwargs):
    global lock
    with lock:
        if settings.get_settings().cached_disabled:
            return None
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.close(*args, **kwargs)


def touch(*args, **kwargs):
    global lock
    with lock:
        if settings.get_settings().cached_disabled:
            return None
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.touch(*args, **kwargs)
