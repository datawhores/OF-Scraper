import pathlib
import shutil

import ofscraper.utils.settings as settings
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths


# config.json's save locations, keyed on the file and its modification time:
# the check runs often, and the file is read again only once it changes.
# One (key, value) tuple, replaced whole, so a thread reading it never finds
# the value of another key or none at all
_save_locations = (None, None)


def _get_save_locations():
    global _save_locations
    config = pathlib.Path(common_paths.get_config_path())
    try:
        key = (str(config), config.stat().st_mtime_ns)
    except OSError:
        key = (str(config), None)
    cached = _save_locations
    if cached[0] != key:
        cached = (key, tuple(dict.fromkeys(common_paths.get_save_locations().values())))
        _save_locations = cached
    return cached[1]


def get_check_paths():
    """OFSC_DISK_SPACE_CHECK_PATH when set, else the disk of each folder files
    are saved under: save_location and the live_options and type_options
    ones. A folder not made yet is measured on its nearest existing folder,
    which is on the same disk; a link is followed first, even to a folder
    that's missing, so the disk is the target's."""
    path = of_env.getattr("DISK_SPACE_CHECK_PATH")
    if path:
        return [path]
    out = []
    for location in _get_save_locations():
        path = pathlib.Path(location).resolve()
        while not path.exists() and path.parent != path:
            path = path.parent
        out.append(path)
    return list(dict.fromkeys(out))


def get_free():
    """The free space on the fullest of those disks"""
    return min(shutil.disk_usage(path).free for path in get_check_paths())


def space_checker(func):
    def inner(*args, **kwargs):
        if not check_free_size():
            alert_full()
            raise Exception("Space min has been reached")
        return func(*args, **kwargs)

    return inner


def alert_full():
    import ofscraper.main.close.alerts as alerts

    alerts.failing(alerts.DISK_FULL, "The free-space limit was reached; downloads stopped")


def check_free_size():
    space_limit = settings.get_settings().system_free_min
    if space_limit > 0 and space_limit > get_free():
        return False
    return True
