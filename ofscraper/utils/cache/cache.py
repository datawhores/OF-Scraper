import threading

from diskcache import Cache

import ofscraper.utils.config.data as data
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings

cache = None
lock = threading.Lock()


def get(*args, **kwargs):
    global lock
    lock.acquire()
    try:
        if settings.get_settings().cached_disabled:
            return kwargs.get("default")
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        value = cache.get(*args, **kwargs)
        # diskcache keeps one sqlite connection per thread; worker threads
        # never closed theirs (set() already closes after writing)
        if threading.current_thread() is not threading.main_thread():
            cache.close()
        return value
    except Exception as E:
        raise E
    finally:
        lock.release()


def set(*args, auto_close=True, **kwargs):
    global lock
    lock.acquire()
    try:
        if settings.get_settings().cached_disabled:
            return
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.set(*args, **kwargs)
    except Exception as E:
        raise E
    finally:
        lock.release()
    if auto_close:
        close()


def close(*args, **kwargs):
    global lock
    lock.acquire()
    try:
        if settings.get_settings().cached_disabled:
            return None
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.close(*args, **kwargs)
    except Exception as E:
        raise E
    finally:
        lock.release()


def touch(*args, **kwargs):
    global lock
    lock.acquire()
    try:
        if settings.get_settings().cached_disabled:
            return None
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.touch(*args, **kwargs)

    except Exception as E:
        raise E
    finally:
        lock.release()
