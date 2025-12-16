#
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


@wrapper.config_reader
def get_main_profile(config=None):
    if config is False:
        return of_env.getattr("PROFILE_DEFAULT")

    value = config.get(of_env.getattr("mainProfile"))
    return value or of_env.getattr("PROFILE_DEFAULT")


@wrapper.config_reader
def get_filesize_max(config=None):
    if config is False:
        return of_env.getattr("FILE_SIZE_MAX_DEFAULT")
    try:
        size = config.get("file_size_max")
        if size is None:
            size = config.get("download_options", {}).get("file_size_max")
        if size is None:
            size = config.get("download_options", {}).get("file_size_limit")  # Legacy
        if size is None:
            size = config.get("content_filter_options", {}).get("file_size_max")

        final_size = (
            size if size is not None else of_env.getattr("FILE_SIZE_MAX_DEFAULT")
        )
        return parse_size(str(final_size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_filesize_min(config=None):
    if config is False:
        return of_env.getattr("FILE_SIZE_MIN_DEFAULT")
    try:
        size = config.get("file_size_min")
        if size is None:
            size = config.get("download_options", {}).get("file_size_min")
        if size is None:
            size = config.get("content_filter_options", {}).get("file_size_min")

        final_size = (
            size if size is not None else of_env.getattr("FILE_SIZE_MIN_DEFAULT")
        )
        return parse_size(str(final_size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_min_length(config=None):
    if config is False:
        return of_env.getattr("MIN_LENGTH_DEFAULT")

    value = config.get("length_min")
    if value is None:
        value = config.get("download_options", {}).get("length_min")
    if value is None:
        value = config.get("content_filter_options", {}).get("length_min")

    return value if value is not None else of_env.getattr("MIN_LENGTH_DEFAULT")


@wrapper.config_reader
def get_max_length(config=None):
    if config is False:
        return of_env.getattr("MAX_LENGTH_DEFAULT")

    value = config.get("length_max")
    if value is None:
        value = config.get("download_options", {}).get("length_max")
    if value is None:
        value = config.get("content_filter_options", {}).get("length_max")

    return value if value is not None else of_env.getattr("MAX_LENGTH_DEFAULT")


@wrapper.config_reader
def get_system_freesize(config=None):
    if config is False:
        return of_env.getattr("SYSTEM_FREEMIN_DEFAULT")
    try:
        size = config.get("system_free_min")
        if size is None:
            size = config.get("download_options", {}).get("system_free_min")

        final_size = (
            size if size is not None else of_env.getattr("SYSTEM_FREEMIN_DEFAULT")
        )
        return parse_size(str(final_size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_dirformat(config=None):
    if config is False:
        return of_env.getattr("DIR_FORMAT_DEFAULT")
    value = config.get("dir_format")
    if value is None:
        value = config.get("file_options", {}).get("dir_format")
    return value or of_env.getattr("DIR_FORMAT_DEFAULT")


@wrapper.config_reader
def get_fileformat(config=None):
    if config is False:
        return of_env.getattr("FILE_FORMAT_DEFAULT")

    value = config.get("file_format")
    if value is None:
        value = config.get("file_options", {}).get("file_format")

    return value or of_env.getattr("FILE_FORMAT_DEFAULT")


@wrapper.config_reader
def get_textlength(config=None):
    if config is False:
        return of_env.getattr("TEXTLENGTH_DEFAULT")
    try:
        length = config.get("textlength")
        if length is None:
            length = config.get("file_options", {}).get("textlength")

        final_length = (
            length if length is not None else of_env.getattr("TEXTLENGTH_DEFAULT")
        )
        return int(final_length)
    except (ValueError, TypeError):
        return of_env.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None):
    if config is False:
        return of_env.getattr("DATE_DEFAULT")

    value = config.get("date")
    if value is None:
        value = config.get("file_options", {}).get("date")

    return value or of_env.getattr("DATE_DEFAULT")


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    if config is False:
        return of_env.getattr("INFINITE_LOOP_DEFAULT")

    val = config.get("infinite_loop_action_mode")
    if val is None:
        val = config.get("advanced_options", {}).get("infinite_loop_action_mode")

    return val if val is not None else of_env.getattr("INFINITE_LOOP_DEFAULT")


@wrapper.config_reader
def get_enable_after(config=None):
    if config is False:
        return of_env.getattr("ENABLE_AUTO_AFTER_DEFAULT")

    val = config.get("enable_auto_after")
    if val is None:
        val = config.get("advanced_options", {}).get("enable_auto_after")

    return val if val is not None else of_env.getattr("ENABLE_AUTO_AFTER_DEFAULT")


@wrapper.config_reader
def get_default_userlist(config=None):
    if config is False:
        raw_value = of_env.getattr("DEFAULT_USER_LIST")
    else:
        config_value = config.get("default_user_list")
        if config_value is None:
            config_value = config.get("advanced_options", {}).get("default_user_list")

        raw_value = config_value or of_env.getattr("DEFAULT_USER_LIST")
    return raw_value or []


@wrapper.config_reader
def get_default_blacklist(config=None):
    if config is False:
        raw_value = of_env.getattr("DEFAULT_BLACK_LIST")
    else:
        config_value = config.get("default_black_list")
        if config_value is None:
            config_value = config.get("advanced_options", {}).get("default_black_list")

        raw_value = config_value or of_env.getattr("DEFAULT_BLACK_LIST")

    return raw_value or []


@wrapper.config_reader
def get_logs_expire(config=None):
    if not config:
        return None

    val = config.get("logs_expire_time")
    if val is None:
        val = config.get("advanced_options", {}).get("logs_expire_time")
    return int(val) if val is not None else 0


@wrapper.config_reader
def get_ssl_verify(config=None):
    if not config:
        return of_env.getattr("SSL_VALIDATION_DEFAULT")

    val = config.get("ssl_verify")
    if val is None:
        val = config.get("advanced_options", {}).get("ssl_verify")

    return val if val is not None else of_env.getattr("SSL_VALIDATION_DEFAULT")


@wrapper.config_reader
def get_after_action_script(config=None):
    if config is False:
        return of_env.getattr("AFTER_ACTION_SCRIPT_DEFAULT")

    val = config.get("after_action_script")
    if val is None:
        val = config.get("advanced_options", {}).get("after_action_script")
    if val is None:
        val = config.get("script_options", {}).get("after_action_script")

    return val if val is not None else of_env.getattr("AFTER_ACTION_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_post_script(config=None):
    if config is False:
        return of_env.getattr("POST_SCRIPT_DEFAULT")

    val = config.get("post_script")
    if val is None:
        val = config.get("advanced_options", {}).get("post_script")
    if val is None:
        val = config.get("scripts", {}).get("post_script")
    if val is None:
        val = config.get("script_options", {}).get("post_script")

    return val if val is not None else of_env.getattr("POST_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_naming_script(config=None):
    if config is False:
        return of_env.getattr("NAMING_SCRIPT_DEFAULT")

    val = config.get("naming_script")
    if val is None:
        val = config.get("advanced_options", {}).get("naming_script")
    if val is None:
        val = config.get("scripts", {}).get("naming_script")
    if val is None:
        val = config.get("script_options", {}).get("naming_script")

    return val if val is not None else of_env.getattr("NAMING_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_skip_download_script(config=None):
    if config is False:
        return of_env.getattr("SKIP_DOWNLOAD_SCRIPT_DEFAULT")

    val = config.get("skip_download_script")
    if val is None:
        val = config.get("advanced_options", {}).get("skip_download_script")
    if val is None:
        val = config.get("scripts", {}).get("skip_download_script")
    if val is None:
        val = config.get("script_options", {}).get("skip_download_script")

    return val if val is not None else of_env.getattr("SKIP_DOWNLOAD_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_after_download_script(config=None):
    if config is False:
        return of_env.getattr("AFTER_DOWNLOAD_SCRIPT_DEFAULT")

    val = config.get("after_download_script")
    if val is None:
        val = config.get("advanced_options", {}).get("after_download_script")
    if val is None:
        val = config.get("scripts", {}).get("after_download_script")
    if val is None:
        val = config.get("script_options", {}).get("after_download_script")

    return val if val is not None else of_env.getattr("AFTER_DOWNLOAD_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_env_files(config=None):
    if config is False:
        raw_value = of_env.getattr("ENV_FILES_DEFAULT")
    else:
        config_value = config.get("env_files")
        if config_value is None:
            config_value = config.get("advanced_options", {}).get("env_files")
        if config_value is None:
            config_value = config.get("scripts", {}).get("env_files")
        if config_value is None:
            config_value = config.get("script_options", {}).get("env_files")

        raw_value = (
            config_value
            if config_value is not None
            else of_env.getattr("ENV_FILES_DEFAULT")
        )
    return raw_value or []


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
        limit = config.get("download_limit")
        if limit is None:
            limit = config.get("performance_options", {}).get("download_limit")

        final_limit = (
            limit if limit is not None else of_env.getattr("DOWNLOAD_LIMIT_DEFAULT")
        )
        return parse_size(str(final_limit))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config is False:
        return of_env.getattr("FFMPEG_DEFAULT")

    val = config.get("ffmpeg")
    if val is None:
        val = config.get("binary_options", {}).get("ffmpeg")

    return val if val is not None else of_env.getattr("FFMPEG_DEFAULT")


@wrapper.config_reader
def get_discord(config=None):
    if config is False:
        return of_env.getattr("DISCORD_DEFAULT")

    val = config.get("discord")
    return val if val is not None else of_env.getattr("DISCORD_DEFAULT", "")


@wrapper.config_reader
def get_filter(config=None):
    if config is False:
        return of_env.getattr("FILTER_DEFAULT")

    filter_val = config.get("filter")
    if filter_val is None:
        filter_val = config.get("download_options", {}).get("filter")
    if filter_val is None:
        filter_val = config.get("content_filter_options", {}).get("filter")

    final_filter = (
        filter_val if filter_val is not None else of_env.getattr("FILTER_DEFAULT")
    )

    if isinstance(final_filter, str):
        return [x.capitalize().strip() for x in final_filter.split(",")]
    elif isinstance(final_filter, list):
        return [x.capitalize() for x in final_filter]
    return []


@wrapper.config_reader
def responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")

    val = config.get("responsetype")
    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")


@wrapper.config_reader
def get_timeline_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]

    val = config.get("timeline")
    if val is None:
        val = config.get("post")
    if val is None:
        val = config.get("responsetype", {}).get("timeline")
    if val is None:
        val = config.get("responsetype", {}).get("post")
    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]


@wrapper.config_reader
def get_post_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]

    val = config.get("post")
    if val is None:
        val = config.get("timeline")
    if val is None:
        val = config.get("responsetype", {}).get("post")
    if val is None:
        val = config.get("responsetype", {}).get("timeline")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]


@wrapper.config_reader
def get_archived_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]

    val = config.get("archived")
    if val is None:
        val = config.get("responsetype", {}).get("archived")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]


@wrapper.config_reader
def get_stories_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]

    val = config.get("stories")
    if val is None:
        val = config.get("responsetype", {}).get("stories")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]


@wrapper.config_reader
def get_highlights_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]

    val = config.get("highlights")
    if val is None:
        val = config.get("responsetype", {}).get("highlights")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]


@wrapper.config_reader
def get_paid_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]

    val = config.get("paid")
    if val is None:
        val = config.get("responsetype", {}).get("paid")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]


@wrapper.config_reader
def get_messages_progress_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["message"]

    val = config.get("message")
    if val is None:
        val = config.get("responsetype", {}).get("message")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["message"]


@wrapper.config_reader
def get_profile_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]

    val = config.get("profile")
    if val is None:
        val = config.get("responsetype", {}).get("profile")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]


@wrapper.config_reader
def get_pinned_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]

    val = config.get("pinned")
    if val is None:
        val = config.get("responsetype", {}).get("pinned")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]


@wrapper.config_reader
def get_streams_responsetype(config=None):
    if config is False:
        return of_env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]

    val = config.get("streams")
    if val is None:
        val = config.get("responsetype", {}).get("streams")

    return val or of_env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]


@wrapper.config_reader
def get_spacereplacer(config=None):
    if config is False:
        return of_env.getattr("SPACE_REPLACER_DEFAULT")

    val = config.get("space_replacer")
    if val is None:
        val = config.get("file_options", {}).get("space_replacer")
    if val is None:
        val = config.get("file_options", {}).get("space-replacer")  # Legacy

    return val or of_env.getattr("SPACE_REPLACER_DEFAULT")


@wrapper.config_reader
def get_private_key(config=None):
    if config is None or config is False:
        return None

    val = config.get("private-key")
    if val is None:
        val = config.get("cdm_options", {}).get("private-key")
    return val


@wrapper.config_reader
def get_client_id(config=None):
    if config is None or config is False:
        return None

    val = config.get("client-id")
    if val is None:
        val = config.get("cdm_options", {}).get("client-id")
    return val


@wrapper.config_reader
def get_key_mode(config=None):
    if config is False:
        return of_env.getattr("KEY_DEFAULT")

    value = config.get("key-mode-default")
    if value is None:
        value = config.get("cdm_options", {}).get("key-mode-default")

    final_value = value if value is not None else of_env.getattr("KEY_DEFAULT")
    return (
        final_value.lower()
        if final_value and final_value.lower() in const.KEY_OPTIONS
        else of_env.getattr("KEY_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config is False:
        return of_env.getattr("DYNAMIC_RULE_DEFAULT")

    value = config.get("dynamic-mode-default")
    if value is None:
        value = config.get("advanced_options", {}).get("dynamic-mode-default")

    final_value = value if value is not None else of_env.getattr("DYNAMIC_RULE_DEFAULT")
    return (
        final_value.lower()
        if final_value and final_value.lower() in of_env.getattr("DYNAMIC_OPTIONS_ALL")
        else of_env.getattr("DYNAMIC_RULE_DEFAULT")
    )


@wrapper.config_reader
def get_part_file_clean(config=None):
    if config is False:
        return of_env.getattr("RESUME_DEFAULT")

    val = config.get("auto_resume")
    if val is None:
        val = config.get("download_options", {}).get("auto_resume")

    if val is not None:
        return val

    # Legacy support
    legacy_val = config.get("partfileclean")
    if legacy_val is not None:
        return legacy_val is False

    return of_env.getattr("RESUME_DEFAULT")


@wrapper.config_reader
def get_download_semaphores(config=None):
    if config is False:
        return of_env.getattr("DOWNLOAD_SEM_DEFAULT")
    try:
        sem = config.get("download_sems")
        if sem is None:
            sem = config.get("performance_options", {}).get("download_sems")

        final_sem = sem if sem is not None else of_env.getattr("DOWNLOAD_SEM_DEFAULT")
        return int(final_sem)
    except (ValueError, TypeError):
        return int(of_env.getattr("DOWNLOAD_SEM_DEFAULT"))


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    if config is False:
        return of_env.getattr("PROGRESS_DEFAULT")

    val = config.get("downloadbars")
    if val is None:
        val = config.get("advanced_options", {}).get("downloadbars")

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

    data = config.get("cache-mode")
    if data is None:
        data = config.get("advanced_options", {}).get("cache-mode")

    final_data = data if data is not None else of_env.getattr("CACHEDEFAULT")

    if final_data in {"sqlite", "json", "disabled"}:
        return final_data
    else:
        return of_env.getattr("CACHEDEFAULT")


@wrapper.config_reader
def get_rotate_logs(config=None):
    if config is False:
        return of_env.getattr("ROTATE_DEFAULT")

    value = config.get("rotate_logs")
    if value is None:
        value = config.get("advanced_options", {}).get("rotate_logs")

    return value if value is not None else of_env.getattr("ROTATE_DEFAULT")


@wrapper.config_reader
def get_sanitizeDB(config=None):
    if config is False:
        return of_env.getattr("SANITIZE_DB_DEFAULT")

    val = config.get("sanitize_text")
    if val is None:
        val = config.get("advanced_options", {}).get("sanitize_text")

    return val if val is not None else of_env.getattr("SANITIZE_DB_DEFAULT")


@wrapper.config_reader
def get_textType(config=None):
    if config is False:
        return of_env.getattr("TEXT_TYPE_DEFAULT")

    value = config.get("text_type_default")
    if value is None:
        value = config.get("file_options", {}).get("text_type_default")

    final_value = value if value is not None else of_env.getattr("TEXT_TYPE_DEFAULT")
    return (
        final_value
        if final_value in {"letter", "word"}
        else of_env.getattr("TEXT_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_TempDir(config=None):
    if config is False:
        return of_env.getattr("TEMP_FOLDER_DEFAULT")

    val = config.get("temp_dir")
    if val is None:
        val = config.get("advanced_options", {}).get("temp_dir")

    return val if val is not None else of_env.getattr("TEMP_FOLDER_DEFAULT")


@wrapper.config_reader
def get_truncation(config=None):
    if config is False:
        return of_env.getattr("TRUNCATION_DEFAULT")

    val = config.get("truncation_default")
    if val is None:
        val = config.get("file_options", {}).get("truncation_default")

    return val if val is not None else of_env.getattr("TRUNCATION_DEFAULT")


@wrapper.config_reader
def get_max_post_count(config=None):
    if config is False:
        return of_env.getattr("MAX_COUNT_DEFAULT")
    try:
        count = config.get("max_post_count")
        if count is None:
            count = config.get("download_options", {}).get("max_post_count")

        final_count = (
            count if count is not None else of_env.getattr("MAX_COUNT_DEFAULT")
        )
        return int(final_count)
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
