import logging
import shutil
import traceback

import ofscraper.utils.paths.common as common_paths


def make_folders():
    common_paths.get_config_folder()
    create_profile_path()


def create_profile_path(name=None):
    out = common_paths.get_profile_path(name)
    out.mkdir(exist_ok=True, parents=True)
    return out


def copy_path(source, dst):
    try:
        shutil.copy2(source, dst)
    except OSError as e:
        logging.getLogger("shared").debug("failed to copy with copy2 using copy")
        logging.getLogger("shared").traceback_(e)
        logging.getLogger("shared").traceback_(traceback.format_exc())
        shutil.copy(source, dst)
    except Exception as e:
        raise e
