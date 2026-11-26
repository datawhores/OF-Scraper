import pathlib
import shutil

import ofscraper.utils.settings as settings
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths


# config.json's save_location, keyed on the file and its modification time:
# the check runs often, and the file is read again only once it changes.
# One (key, value) tuple, replaced whole, so a thread reading it never finds
# the value of another key or none at all
_save_location = (None, None)


def _get_save_location():
    global _save_location
    config = pathlib.Path(common_paths.get_config_path())
    try:
        key = (str(config), config.stat().st_mtime_ns)
    except OSError:
        key = (str(config), None)
    cached = _save_location
    if cached[0] != key:
        cached = (key, common_paths.get_save_location())
        _save_location = cached
    return cached[1]


def measured_at(folder):
    """Where a folder's free space is measured: the folder, or when it isn't
    made yet its nearest existing folder, which is on the same disk; a link
    is followed first, even to a folder that's missing, so the disk is the
    target's."""
    path = pathlib.Path(folder).resolve()
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def get_check_path(folder=None):
    """OFSC_DISK_SPACE_CHECK_PATH when set, else where the free space of
    folder (the folder a file is saved under, which a type_options entry can
    move to another disk) or of save_location is measured"""
    return of_env.getattr("DISK_SPACE_CHECK_PATH") or measured_at(folder or _get_save_location())


def get_free(folder=None):
    return shutil.disk_usage(get_check_path(folder)).free


def space_checker(func):
    def inner(*args, **kwargs):
        if not check_free_size():
            alert_full()
            raise Exception("Space min has been reached")
        return func(*args, **kwargs)

    return inner


def alert_full(folder=None):
    """folder: a type_options save folder whose disk is full, when only the
    files saved there stop"""
    import ofscraper.main.close.alerts as alerts

    if folder is None:
        message = "The free-space limit was reached; downloads stopped"
    else:
        message = "The free-space limit was reached on a type_options save disk; downloads saved there stopped"
    alerts.failing(alerts.DISK_FULL, message)


def check_free_size(folder=None):
    space_limit = settings.get_settings().system_free_min
    if space_limit > 0 and space_limit > get_free(folder):
        return False
    return True


def check_every_disk():
    """True when every disk downloads are saved on is above the limit:
    save_location's and each type_options one's (the livestream ones aren't
    checked: recordings don't stop at the limit). What a disk-full alert
    waits for before it's announced as over."""
    import ofscraper.classes.placeholder as placeholder

    return all(check_free_size(root) for root in placeholder.media_roots())
