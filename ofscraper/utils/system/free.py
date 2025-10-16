import shutil

import ofscraper.utils.settings as settings
import ofscraper.utils.of_env.of_env as of_env


def get_free():
    total, used, free = shutil.disk_usage(of_env.getattr("DISK_SPACE_CHECK_PATH"))
    return free


def space_checker(func):
    def inner(*args, **kwargs):
        if not check_free_size():
            raise Exception("Space min has been reached")
        return func(*args, **kwargs)

    return inner


def check_free_size():
    space_limit = settings.get_settings().system_free_min
    if space_limit > 0 and space_limit > get_free():
        return False
    return True
