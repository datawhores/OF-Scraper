import re

import ofscraper.utils.config.data as data
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.profiles.tools as tools
import ofscraper.utils.settings as settings

currentProfile = None
currentData = None


def get_my_info():
    global currentData
    global currentProfile
    if currentProfile == get_active_profile():
        return currentData
    else:
        import ofscraper.data.api.me as me

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
    if settings.get_settings().profile:
        profile = settings.get_settings().profile
    else:
        profile = get_current_config_profile()
    return tools.profile_name_fixer(profile)
