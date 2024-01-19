import shutil

import ofscraper.utils.config.data as data


def get_free():
    total, used, free = shutil.disk_usage("/")
    return free


def space_checker(func):
    def inner(*args, **kwargs):
        space_limit = data.get_system_freesize()
        if space_limit > 0 and space_limit > get_free():
            raise Exception("Space min has been reached")
        return func(*args, **kwargs)

    return inner
