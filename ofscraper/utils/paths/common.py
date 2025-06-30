import os
import pathlib

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.of_env.of_env as env_attr
import ofscraper.utils.dates as dates_manager
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.profiles.tools as tools
import ofscraper.utils.settings as settings


def getcachepath():
    profile = get_profile_path()
    name = "cache_json" if data.cache_mode_helper() == "json" else "cache_sql"
    path = profile / f"{name}"
    path = pathlib.Path(os.path.normpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_auth_file():
    return get_profile_path() / env_attr.getattr("authFile")


def get_username():
    return pathlib.Path.home().name


def getDB():
    return get_profile_path() / "locks" / "db.lock"


def getRich():
    return get_profile_path() / "locks" / "rich.lock"


def getFile():
    return get_profile_path() / "locks" / "file.lock"


def getDiscord():
    return get_profile_path() / "locks" / "discord.lock"


def getMediaDB():
    return get_profile_path() / "locks" / "media_db.lock"


def get_config_home():
    return get_config_path().parent


def get_config_path():
    configPath = settings.get_args().config
    defaultPath = (
        pathlib.Path.home()
        / of_env.getattr("configPath")
        / of_env.getattr("configFile")
    )
    ofscraperHome = pathlib.Path.home() / of_env.getattr("configPath")

    if configPath is None or configPath == "":
        return defaultPath
    configPath = pathlib.Path(configPath)
    # check if path exists
    if configPath.is_file():
        return configPath
    elif configPath.is_dir():
        return configPath / of_env.getattr("configFile")
    # enforce that configpath needs some extension
    elif configPath.suffix == "":
        return configPath / of_env.getattr("configFile")

    elif str(configPath.parent) == ".":
        return ofscraperHome / configPath
    return configPath


def getlogpath():
    path = None
    if data.get_rotate_logs():
        path = (
            get_log_folder()
            / f'{data.get_main_profile()}_{dates_manager.getLogDate().get("day")}'
            / f'ofscraper_{data.get_main_profile()}_{dates_manager.getLogDate().get("now")}.log'
        )
    else:
        path = (
            get_log_folder()
            / f'ofscraper_{data.get_main_profile()}_{dates_manager.getLogDate().get("day")}.log'
        )
    path = pathlib.Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_log_folder():
    return get_config_home() / "logging"


def get_profile_path(name=None):
    if name:
        profile = get_config_home() / name
    elif not settings.get_settings().profile:
        profile = get_config_home() / profile_data.get_current_config_profile()
    else:
        profile = get_config_home() / settings.get_settings().profile
    return pathlib.Path(tools.profile_name_fixer(profile))


def get_save_location(config=None, mediatype=None):
    if config is False:
        return of_env.getattr("SAVE_PATH_DEFAULT")
    config = config or config_file.open_config()
    return (
        config.get("save_location")
        or config.get("file_options", {}).get("save_location")
        or of_env.getattr("SAVE_PATH_DEFAULT")
    )


def get_config_folder():
    out = get_config_path().parent
    out.mkdir(exist_ok=True, parents=True)
    return out
