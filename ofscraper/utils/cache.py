import threading

from diskcache import Cache

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.paths.common as common_paths

cache = None
lock = threading.Lock()


def get(*args, **kwargs):
    global lock
    lock.acquire()
    try:
        if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
            return kwargs.get("default")
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        return cache.get(*args, **kwargs)
    except Exception as E:
        raise E
    finally:
        lock.release()


def set(*args, **kwargs):
    global lock
    lock.acquire()
    try:
        if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
            return
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.set(*args, **kwargs)
    except Exception as E:
        raise E
    finally:
        lock.release()


def close(*args, **kwargs):
    global lock
    lock.acquire()
    try:
        if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
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
        if read_args.retriveArgs().no_cache or data.get_cache_mode() == "disabled":
            return None
        global cache
        if cache is None:
            cache = Cache(common_paths.getcachepath(), disk=data.get_cache_mode())
        cache.touch(*args, **kwargs)

    except Exception as E:
        raise E
    finally:
        lock.release()
