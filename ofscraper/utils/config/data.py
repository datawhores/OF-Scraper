r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

from diskcache import Disk, JSONDisk
from humanfriendly import parse_size

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.utils.wrapper as wrapper
import ofscraper.utils.const as const

def _to_comma_separated_string(value: any) -> str | None:
    """
    Helper function to convert a list into a comma-separated string.
    If the value is not a list, it's returned as is.
    """
    if isinstance(value, list):
        # Use map(str, ...) to ensure all items in the list are strings before joining
        return ",".join(map(str, value))
    return value

@wrapper.config_reader
def get_main_profile(config=None):
    if config is False:
        return of_env.getattr("PROFILE_DEFAULT")
    return config.get(
        of_env.getattr("mainProfile"), of_env.getattr("PROFILE_DEFAULT")
    ) or of_env.getattr("PROFILE_DEFAULT")


@wrapper.config_reader
def get_filesize_max(config=None):
    if config is False:
        return of_env.getattr("FILE_SIZE_MAX_DEFAULT")
    try:
        size = (
            config.get("file_size_max")
            or config.get("download_options", {}).get("file_size_max")
            or config.get("download_options", {}).get(
                "file_size_limit"
            )  # Legacy support
            or config.get("content_filter_options", {}).get("file_size_max")
            or of_env.getattr("FILE_SIZE_MAX_DEFAULT")
        )
        return parse_size(str(size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_filesize_min(config=None):
    if config is False:
        return of_env.getattr("FILE_SIZE_MIN_DEFAULT")
    try:
        size = (
            config.get("file_size_min")
            or config.get("download_options", {}).get("file_size_min")
            or config.get("content_filter_options", {}).get("file_size_min")
            or of_env.getattr("FILE_SIZE_MIN_DEFAULT")
        )
        return parse_size(str(size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_min_length(config=None):
    if config is False:
        return of_env.getattr("MIN_LENGTH_DEFAULT")
    return (
        config.get("length_min")
        or config.get("download_options", {}).get("length_min")
        or config.get("content_filter_options", {}).get("length_min")
    )


@wrapper.config_reader
def get_max_length(config=None):
    if config is False:
        return of_env.getattr("MAX_LENGTH_DEFAULT")
    return (
        config.get("length_max")
        or config.get("download_options", {}).get("length_max")
        or config.get("content_filter_options", {}).get("length_max")
    )


@wrapper.config_reader
def get_system_freesize(config=None):
    if config is False:
        return of_env.getattr("SYSTEM_FREEMIN_DEFAULT")
    try:
        size = (
            config.get("system_free_min")
            or config.get("download_options", {}).get("system_free_min")
            or of_env.getattr("SYSTEM_FREEMIN_DEFAULT")
        )
        return parse_size(str(size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_dirformat(config=None):
    if config is False:
        return of_env.getattr("DIR_FORMAT_DEFAULT")
    return (
        config.get("dir_format")
        or config.get("file_options", {}).get("dir_format")
        or of_env.getattr("DIR_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_fileformat(config=None):
    if config is False:
        return of_env.getattr("FILE_FORMAT_DEFAULT")
    return (
        config.get("file_format")
        or config.get("file_options", {}).get("file_format")
        or of_env.getattr("FILE_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_textlength(config=None):
    if config is False:
        return of_env.getattr("TEXTLENGTH_DEFAULT")
    try:
        length = (
            config.get("textlength")
            or config.get("file_options", {}).get("textlength")
            or of_env.getattr("TEXTLENGTH_DEFAULT")
        )
        return int(length)
    except (ValueError, TypeError):
        return of_env.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None):
    if config is False:
        return of_env.getattr("DATE_DEFAULT")
    return (
        config.get("date")
        or config.get("file_options", {}).get("date")
        or of_env.getattr("DATE_DEFAULT")
    )


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    if config is False:
        return of_env.getattr("INFINITE_LOOP_DEFAULT")
    val = config.get("infinite_loop_action_mode") or config.get(
        "advanced_options", {}
    ).get("infinite_loop_action_mode")
    return val if val is not None else of_env.getattr("INFINITE_LOOP_DEFAULT")


@wrapper.config_reader
def get_enable_after(config=None):
    if config is False:
        return of_env.getattr("ENABLE_AUTO_AFTER_DEFAULT")
    val = config.get("enable_auto_after") or config.get("advanced_options", {}).get(
        "enable_auto_after"
    )
    return val if val is not None else of_env.getattr("ENABLE_AUTO_AFTER_DEFAULT")


@wrapper.config_reader
def get_default_userlist(config=None):
    """
    Retrieves the default user list.
    It checks the config first, and only uses the environment variable as a fallback.
    Converts list values to a comma-separated string.
    """
    if config is False:
        raw_value = of_env.getattr("DEFAULT_USER_LIST")
    else:
        # First, attempt to get the value from any of the config locations.
        config_value = (
            config.get("default_user_list")
            or config.get("advanced_options", {}).get("default_user_list")
        )

        # Fallback to the environment variable only if no value was found in the config.
        raw_value = config_value if config_value is not None else of_env.getattr("DEFAULT_USER_LIST")

    # Format the found value
    formatted_value = _to_comma_separated_string(raw_value)

    # Ensure a string is always returned
    return formatted_value or ""

@wrapper.config_reader
def get_default_blacklist(config=None):
    """
    Retrieves the default blacklist.
    It checks the config first, and only uses the environment variable as a fallback.
    Converts list values to a comma-separated string.
    """
    if config is False:
        raw_value = of_env.getattr("DEFAULT_BLACK_LIST")
    else:
        # First, attempt to get the value from any of the config locations.
        config_value = (
            config.get("default_black_list")
            or config.get("advanced_options", {}).get("default_black_list")
        )

        # Use the config value if it exists (even if it's "" or []),
        # otherwise, fall back to the environment variable.
        raw_value = config_value if config_value is not None else of_env.getattr("DEFAULT_BLACK_LIST")

    # Format the found value (which could be a list, str, or None)
    formatted_value = _to_comma_separated_string(raw_value)

    # Ensure we always return a string, defaulting to ""
    return formatted_value or ""


@wrapper.config_reader
def get_logs_expire(config=None):
    if not config:
        return None
    return config.get("logs_expire_time") or config.get("advanced_options", {}).get(
        "logs_expire_time"
    )


@wrapper.config_reader
def get_ssl_verify(config=None):
    if not config:
        return of_env.getattr("SSL_VALIDATION_DEFAULT")
    val = config.get("ssl_verify") or config.get("advanced_options", {}).get(
        "ssl_verify"
    )
    # Return False if val is None, otherwise return the boolean value of val
    return bool(val)


@wrapper.config_reader
def get_after_action_script(config=None):
    if config is False:
        return of_env.getattr("AFTER_ACTION_SCRIPT_DEFAULT")
    return (
        config.get("after_action_script")
        or config.get("advanced_options", {}).get("after_action_script")
        or config.get("script_options", {}).get("after_action_script")
        or of_env.getattr("AFTER_ACTION_SCRIPT_DEFAULT")
    )


@wrapper.config_reader
def get_post_script(config=None):
    if config is False:
        return of_env.getattr("POST_SCRIPT_DEFAULT")
    return (
        config.get("post_script")
        or config.get("advanced_options", {}).get("post_script")
        or config.get("scripts", {}).get("post_script")
        or config.get("script_options", {}).get("post_script")
        or of_env.getattr("POST_SCRIPT_DEFAULT")
    )


@wrapper.config_reader
def get_naming_script(config=None):
    if config is False:
        return of_env.getattr("NAMING_SCRIPT_DEFAULT")
    return (
        config.get("naming_script")
        or config.get("advanced_options", {}).get("naming_script")
        or config.get("scripts", {}).get("naming_script")
        or config.get("script_options", {}).get("naming_script")
        or of_env.getattr("NAMING_SCRIPT_DEFAULT")
    )


@wrapper.config_reader
def get_skip_download_script(config=None):
    if config is False:
        return of_env.getattr("SKIP_DOWNLOAD_SCRIPT_DEFAULT")
    return (
        config.get("skip_download_script")
        or config.get("advanced_options", {}).get("skip_download_script")
        or config.get("scripts", {}).get("skip_download_script")
        or config.get("script_options", {}).get("skip_download_script")
        or of_env.getattr("SKIP_DOWNLOAD_SCRIPT_DEFAULT")
    )


@wrapper.config_reader
def get_after_download_script(config=None):
    if config is False:
        return of_env.getattr("AFTER_DOWNLOAD_SCRIPT_DEFAULT")
    return (
        config.get("after_download_script")
        or config.get("advanced_options", {}).get("after_download_script")
        or config.get("scripts", {}).get("after_download_script")
        or config.get("script_options", {}).get("after_download_script")
        or of_env.getattr("AFTER_DOWNLOAD_SCRIPT_DEFAULT")
    )
@wrapper.config_reader
def get_env_files(config=None):
    """
    Retrieves the list of environment files to load.
    It checks multiple config locations first, and only uses the environment variable as a fallback.
    Converts list values to a comma-separated string.
    """
    if config is False:
        raw_value = of_env.getattr("ENV_FILES_DEFAULT")
    else:
        # Exhaust all possible config locations first.
        config_value = (
            config.get("env_files")
            or config.get("advanced_options", {}).get("env_files")
            or config.get("scripts", {}).get("env_files")
            or config.get("script_options", {}).get("env_files")
        )

        # Only if the config value is None, use the environment variable.
        raw_value = config_value if config_value is not None else of_env.getattr("ENV_FILES_DEFAULT")

    # Format the final value.
    formatted_value = _to_comma_separated_string(raw_value)

    # Ensure a string is always returned.
    return formatted_value or ""



@wrapper.config_reader
def get_metadata(config=None):
    if config is False:
        return of_env.getattr("METADATA_DEFAULT")
    return config.get("metadata", of_env.getattr("METADATA_DEFAULT"))


@wrapper.config_reader
def get_download_limit(config=None):
    if config is False:
        return of_env.getattr("DOWNLOAD_LIMIT_DEFAULT")
    try:
        limit = (
            config.get("download_limit")
            or config.get("performance_options", {}).get("download_limit")
            or of_env.getattr("DOWNLOAD_LIMIT_DEFAULT")
        )
        return parse_size(str(limit))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config is False:
        return of_env.getattr("FFMPEG_DEFAULT")
    return (
        config.get("ffmpeg")
        or config.get("binary_options", {}).get("ffmpeg")
        or of_env.getattr("FFMPEG_DEFAULT")
    )


@wrapper.config_reader
def get_discord(config=None):
    if config is False:
        return of_env.getattr("DISCORD_DEFAULT")
    return config.get("discord") or of_env.getattr("DISCORD_DEFAULT") or ""


@wrapper.config_reader
def get_filter(config=None):
    if config is False:
        return of_env.getattr("FILTER_DEFAULT")
    filter_val = (
        config.get("filter")
        or config.get("download_options", {}).get("filter")
        or config.get("content_filter_options", {}).get("filter")
        or of_env.getattr("FILTER_DEFAULT")
    )
    if isinstance(filter_val, str):
        return [x.capitalize().strip() for x in filter_val.split(",")]
    elif isinstance(filter_val, list):
        return [x.capitalize() for x in filter_val]
    return []


@wrapper.config_reader
def responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")
    return config.get("responsetype") or of_env.getattr("RESPONSE_TYPE_DEFAULT")


@wrapper.config_reader
def get_timeline_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    return (
        config.get("timeline")
        or config.get("post")
        or config.get("responsetype", {}).get("timeline")
        or config.get("responsetype", {}).get("post")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_post_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    return (
        config.get("post")
        or config.get("timeline")
        or config.get("responsetype", {}).get("post")
        or config.get("responsetype", {}).get("timeline")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_archived_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    return (
        config.get("archived")
        or config.get("responsetype", {}).get("archived")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    )


@wrapper.config_reader
def get_stories_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    return (
        config.get("stories")
        or config.get("responsetype", {}).get("stories")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    )


@wrapper.config_reader
def get_highlights_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    return (
        config.get("highlights")
        or config.get("responsetype", {}).get("highlights")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    )


@wrapper.config_reader
def get_paid_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    return (
        config.get("paid")
        or config.get("responsetype", {}).get("paid")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    )


@wrapper.config_reader
def get_messages_progress_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    return (
        config.get("message")
        or config.get("responsetype", {}).get("message")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    )


@wrapper.config_reader
def get_profile_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    return (
        config.get("profile")
        or config.get("responsetype", {}).get("profile")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    )


@wrapper.config_reader
def get_pinned_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    return (
        config.get("pinned")
        or config.get("responsetype", {}).get("pinned")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    )


@wrapper.config_reader
def get_streams_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]
    return (
        config.get("streams")
        or config.get("responsetype", {}).get("streams")
        or of_env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]
    )


@wrapper.config_reader
def get_spacereplacer(config=None):
    if config is False:
        return of_env.getattr("SPACE_REPLACER_DEFAULT")
    return (
        config.get("space_replacer")
        or config.get("file_options", {}).get("space_replacer")
        or config.get("file_options", {}).get("space-replacer")  # Legacy support
        or of_env.getattr("SPACE_REPLACER_DEFAULT")
    )


@wrapper.config_reader
def get_private_key(config=None):
    if config is None or config is False:
        return None
    return config.get("private-key") or config.get("cdm_options", {}).get("private-key")


@wrapper.config_reader
def get_client_id(config=None):
    if config is None or config is False:
        return None
    return config.get("client-id") or config.get("cdm_options", {}).get("client-id")


@wrapper.config_reader
def get_key_mode(config=None):
    if config is False:
        return of_env.getattr("KEY_DEFAULT")
    value = (
        config.get("key-mode-default")
        or config.get("cdm_options", {}).get("key-mode-default")
        or of_env.getattr("KEY_DEFAULT")
    )
    return (
        value.lower()
        if value and value.lower() in const.KEY_OPTIONS
        else of_env.getattr("KEY_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config is False:
        return of_env.getattr("DYNAMIC_RULE_DEFAULT")
    value = (
        config.get("dynamic-mode-default")
        or config.get("advanced_options", {}).get("dynamic-mode-default")
        or of_env.getattr("DYNAMIC_RULE_DEFAULT")
    )
    return (
        value.lower()
        if value and value.lower() in of_env.getattr("DYNAMIC_OPTIONS_ALL")
        else of_env.getattr("DYNAMIC_RULE_DEFAULT")
    )


@wrapper.config_reader
def get_part_file_clean(config=None):
    if config is False:
        return of_env.getattr("RESUME_DEFAULT")
    val = config.get("auto_resume") or config.get("download_options", {}).get(
        "auto_resume"
    )
    if val is not None:
        return val
    # Legacy support
    if config.get("partfileclean") is not None:
        return config.get("partfileclean") is False
    return of_env.getattr("RESUME_DEFAULT")


@wrapper.config_reader
def get_download_semaphores(config=None):
    if config is False:
        return of_env.getattr("DOWNLOAD_SEM_DEFAULT")
    try:
        sem = (
            config.get("download_sems")
            or config.get("performance_options", {}).get("download_sems")
            or of_env.getattr("DOWNLOAD_SEM_DEFAULT")
        )
        return int(sem)
    except (ValueError, TypeError):
        return int(of_env.getattr("DOWNLOAD_SEM_DEFAULT"))


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    if config is False:
        return of_env.getattr("PROGRESS_DEFAULT")
    val = config.get("downloadbars") or config.get("advanced_options", {}).get(
        "downloadbars"
    )
    return val if val is not None else of_env.getattr("PROGRESS_DEFAULT")


@wrapper.config_reader
def get_cache_mode(config=None):
    if cache_mode_helper(config=config) == "sqlite":
        return Disk
    else:
        return JSONDisk


def cache_mode_helper(config=None):
    if config is False:
        return of_env.getattr("CACHEDEFAULT")
    if config is None:
        config = config_file.open_config()
    data = (
        config.get("cache-mode")
        or config.get("advanced_options", {}).get("cache-mode")
        or of_env.getattr("CACHEDEFAULT")
    )
    if data in {"sqlite", "json"}:
        return data
    elif data == "disabled":
        return data
    else:
        return of_env.getattr("CACHEDEFAULT")


@wrapper.config_reader
def get_rotate_logs(config=None):
    if config is False:
        return of_env.getattr("ROTATE_DEFAULT")
    value = config.get("rotate_logs") or config.get("advanced_options", {}).get(
        "rotate_logs"
    )
    return value if value is not None else of_env.getattr("ROTATE_DEFAULT")


@wrapper.config_reader
def get_sanitizeDB(config=None):
    if config is False:
        return of_env.getattr("SANITIZE_DB_DEFAULT")
    val = config.get("sanitize_text") or config.get("advanced_options", {}).get(
        "sanitize_text"
    )
    return val if val is not None else of_env.getattr("SANITIZE_DB_DEFAULT")


@wrapper.config_reader
def get_textType(config=None):
    if config is False:
        return of_env.getattr("TEXT_TYPE_DEFAULT")
    value = (
        config.get("text_type_default")
        or config.get("file_options", {}).get("text_type_default")
        or of_env.getattr("TEXT_TYPE_DEFAULT")
    )
    return value if value in {"letter", "word"} else of_env.getattr("TEXT_TYPE_DEFAULT")


@wrapper.config_reader
def get_TempDir(config=None):
    if config is False:
        return of_env.getattr("TEMP_FOLDER_DEFAULT")
    return (
        config.get("temp_dir")
        or config.get("advanced_options", {}).get("temp_dir")
        or of_env.getattr("TEMP_FOLDER_DEFAULT")
    )


@wrapper.config_reader
def get_truncation(config=None):
    if config is False:
        return of_env.getattr("TRUNCATION_DEFAULT")
    val = config.get("truncation_default") or config.get("file_options", {}).get(
        "truncation_default"
    )
    return val if val is not None else of_env.getattr("TRUNCATION_DEFAULT")



@wrapper.config_reader
def get_max_post_count(config=None):
    if config is False:
        return of_env.getattr("MAX_COUNT_DEFAULT")
    try:
        count = (
            config.get("max_post_count")
            or config.get("download_options", {}).get("max_post_count")
            or of_env.getattr("MAX_COUNT_DEFAULT")
        )
        return int(count)
    except (ValueError, TypeError):
        return of_env.getattr("MAX_COUNT_DEFAULT")


@wrapper.config_reader
def get_hash(config=None):
    if config is False:
        return of_env.getattr("HASHED_DEFAULT")
    val = config.get("remove_hash_match")
    if val is not None:
        return val
    return config.get("advanced_options", {}).get(
        "remove_hash_match", of_env.getattr("HASHED_DEFAULT")
    )


@wrapper.config_reader
def get_block_ads(config=None):
    if config is False:
        return of_env.getattr("BLOCKED_ADS_DEFAULT")
    val = config.get("block_ads")
    if val is not None:
        return val
    return config.get("content_filter_options", {}).get(
        "block_ads", of_env.getattr("BLOCKED_ADS_DEFAULT")
    )
