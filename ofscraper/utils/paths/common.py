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
    import ofscraper.utils.dry_run as dry_run

    if dry_run.active():
        # a dry run reads and writes a throwaway copy (utils/dry_run.py)
        return dry_run.redirect(path, folder=True)
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
    """
    Determines the correct profile path based on a priority order.
    """
    profile_name = (
        name
        or settings.get_settings().profile
        or profile_data.get_current_config_profile()
    )
    profile = get_config_home() / profile_name
    # Sanitize and return the final path, matching the original function's behavior
    return pathlib.Path(tools.profile_name_fixer(str(profile)))


def get_save_location(config=None):
    if config is False:
        return of_env.getattr("SAVE_PATH_DEFAULT")
    config = config or config_file.open_config()
    return data.strip_path_quotes(
        data._first(config, "save_location", "file_options.save_location")
        or of_env.getattr("SAVE_PATH_DEFAULT")
    )


def get_save_locations(config=None):
    """{setting: folder} for every folder files are saved under: the save
    location, then each live_options and type_options save_location set
    (only the type_options entries downloads use)"""
    from ofscraper.utils.config.naming_check import used_type_options

    if config is None:
        config = config_file.open_config()
    out = {"file_options.save_location": get_save_location(config)}
    overrides = {"live_options.save_location": data.get_live_save_location(config=config)}
    overrides.update(
        (f"type_options.{name}.save_location", section.get("save_location"))
        for name, section in used_type_options(config=config).items()
    )
    out.update((k, v) for k, v in overrides.items() if isinstance(v, str) and v.strip())
    return out


def get_config_folder():
    out = get_config_path().parent
    out.mkdir(exist_ok=True, parents=True)
    return out
