import re

from rich import print

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as data
import ofscraper.utils.paths.common as common_paths

currentProfile = None
currentData = None


def get_my_info():
    global currentData
    global currentProfile
    if currentProfile == get_active_profile():
        return currentData
    else:
        import ofscraper.api.me as me

        currentProfile = get_active_profile()
        currentData = me.scrape_user()
    return currentData


def get_profiles() -> list:
    data.path = common_paths.get_config_home()
    return list(
        filter(
            lambda x: re.search(".*_profile$", str(x)) and x.is_dir(),
            data.path.glob("*"),
        )
    )


def get_profile_names():
    return [profile.name for profile in get_profiles()]


def get_current_config_profile():
    return data.get_main_profile()


def get_active_profile():
    if read_args.retriveArgs().profile:
        return read_args.retriveArgs().profile
    return get_current_config_profile()
