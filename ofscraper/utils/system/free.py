import shutil

import ofscraper.utils.settings as settings


def get_free():
    total, used, free = shutil.disk_usage("/")
    return free


def space_checker(func):
    def inner(*args, **kwargs):
        space_limit = settings.get_settings().system_free_min
        if space_limit > 0 and space_limit > get_free():
            raise Exception("Space min has been reached")
        return func(*args, **kwargs)

    return inner
