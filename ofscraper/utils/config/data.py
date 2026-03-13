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
        size = (
            config.get("file_size_max")
            or config.get("download_options", {}).get("file_size_max")
            or config.get("download_options", {}).get("file_size_limit")
            or config.get("content_filter_options", {}).get("file_size_max")
        )
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
        size = (
            config.get("file_size_min")
            or config.get("download_options", {}).get("file_size_min")
            or config.get("content_filter_options", {}).get("file_size_min")
        )
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
    value = (
        config.get("length_min")
        or config.get("download_options", {}).get("length_min")
        or config.get("content_filter_options", {}).get("length_min")
    )
    return value if value is not None else of_env.getattr("MIN_LENGTH_DEFAULT")


@wrapper.config_reader
def get_max_length(config=None):
    if config is False:
        return of_env.getattr("MAX_LENGTH_DEFAULT")
    value = (
        config.get("length_max")
        or config.get("download_options", {}).get("length_max")
        or config.get("content_filter_options", {}).get("length_max")
    )
    return value if value is not None else of_env.getattr("MAX_LENGTH_DEFAULT")


@wrapper.config_reader
def get_system_freesize(config=None):
    if config is False:
        return of_env.getattr("SYSTEM_FREEMIN_DEFAULT")
    try:
        size = config.get("system_free_min") or config.get("download_options", {}).get(
            "system_free_min"
        )
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
        length = config.get("textlength") or config.get("file_options", {}).get(
            "textlength"
        )
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
def get_incremental_downloads(config=None):
    if config is False:
        return of_env.getattr("INCREMENTAL_DOWNLOADS_DEFAULT")
    val = (
        config.get("incremental_downloads")
        or config.get("advanced_options", {}).get("incremental_downloads")
        or config.get("advanced_options", {}).get("enable_auto_after")
    )
    return val if val is not None else of_env.getattr("INCREMENTAL_DOWNLOADS_DEFAULT")


@wrapper.config_reader
def get_default_userlist(config=None):
    if config is False:
        return of_env.getattr("DEFAULT_USER_LIST") or []
    val = config.get("default_user_list") or config.get("advanced_options", {}).get(
        "default_user_list"
    )
    return val or of_env.getattr("DEFAULT_USER_LIST") or []


@wrapper.config_reader
def get_default_blacklist(config=None):
    if config is False:
        return of_env.getattr("DEFAULT_BLACK_LIST") or []
    val = config.get("default_black_list") or config.get("advanced_options", {}).get(
        "default_black_list"
    )
    return val or of_env.getattr("DEFAULT_BLACK_LIST") or []


@wrapper.config_reader
def get_logs_expire(config=None):
    if not config:
        return 0
    val = config.get("logs_expire_time") or config.get("advanced_options", {}).get(
        "logs_expire_time"
    )
    return int(val) if val is not None else 0


@wrapper.config_reader
def get_ssl_verify(config=None):
    if not config:
        return of_env.getattr("SSL_VALIDATION_DEFAULT")
    
    # 1. Safely check for the key (avoiding 'or' so we don't accidentally skip a literal False)
    val = config.get("ssl_verify")
    if val is None:
        val = config.get("advanced_options", {}).get("ssl_verify")
        
    # 2. Legacy Migration: Convert JSON booleans (True/False) to the new default
    if isinstance(val, bool):
        return "custom"
        
    return val if val is not None else of_env.getattr("SSL_VALIDATION_DEFAULT")


@wrapper.config_reader
def get_after_action_script(config=None):
    if config is False:
        return of_env.getattr("AFTER_ACTION_SCRIPT_DEFAULT")
    val = (
        config.get("after_action_script")
        or config.get("advanced_options", {}).get("after_action_script")
        or config.get("script_options", {}).get("after_action_script")
    )
    return val if val is not None else of_env.getattr("AFTER_ACTION_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_post_script(config=None):
    if config is False:
        return of_env.getattr("POST_SCRIPT_DEFAULT")
    val = (
        config.get("post_script")
        or config.get("advanced_options", {}).get("post_script")
        or config.get("scripts", {}).get("post_script")
        or config.get("script_options", {}).get("post_script")
    )
    return val if val is not None else of_env.getattr("POST_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_naming_script(config=None):
    if config is False:
        return of_env.getattr("NAMING_SCRIPT_DEFAULT")
    val = (
        config.get("naming_script")
        or config.get("advanced_options", {}).get("naming_script")
        or config.get("scripts", {}).get("naming_script")
        or config.get("script_options", {}).get("naming_script")
    )
    return val if val is not None else of_env.getattr("NAMING_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_skip_download_script(config=None):
    if config is False:
        return of_env.getattr("SKIP_DOWNLOAD_SCRIPT_DEFAULT")
    val = (
        config.get("skip_download_script")
        or config.get("advanced_options", {}).get("skip_download_script")
        or config.get("scripts", {}).get("skip_download_script")
        or config.get("script_options", {}).get("skip_download_script")
    )
    return val if val is not None else of_env.getattr("SKIP_DOWNLOAD_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_after_download_script(config=None):
    if config is False:
        return of_env.getattr("AFTER_DOWNLOAD_SCRIPT_DEFAULT")
    val = (
        config.get("after_download_script")
        or config.get("advanced_options", {}).get("after_download_script")
        or config.get("scripts", {}).get("after_download_script")
        or config.get("script_options", {}).get("after_download_script")
    )
    return val if val is not None else of_env.getattr("AFTER_DOWNLOAD_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_env_files(config=None):
    # This must remain "safe" to avoid chicken-and-egg loops
    if config is False:
        return []
    val = (
        config.get("env_files")
        or config.get("advanced_options", {}).get("env_files")
        or config.get("scripts", {}).get("env_files")
        or config.get("script_options", {}).get("env_files")
    )
    return val or []


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
        limit = config.get("download_limit") or config.get(
            "performance_options", {}
        ).get("download_limit")
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
    val = config.get("ffmpeg") or config.get("binary_options", {}).get("ffmpeg")
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
    filter_val = (
        config.get("filter")
        or config.get("download_options", {}).get("filter")
        or config.get("content_filter_options", {}).get("filter")
    )
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
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    if config is False:
        return default
    val = (
        config.get("timeline")
        or config.get("post")
        or config.get("responsetype", {}).get("timeline")
        or config.get("responsetype", {}).get("post")
    )
    return val or default


@wrapper.config_reader
def get_post_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    if config is False:
        return default
    val = (
        config.get("post")
        or config.get("timeline")
        or config.get("responsetype", {}).get("post")
        or config.get("responsetype", {}).get("timeline")
    )
    return val or default


@wrapper.config_reader
def get_archived_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    if config is False:
        return default
    val = config.get("archived") or config.get("responsetype", {}).get("archived")
    return val or default


@wrapper.config_reader
def get_stories_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    if config is False:
        return default
    val = config.get("stories") or config.get("responsetype", {}).get("stories")
    return val or default


@wrapper.config_reader
def get_highlights_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    if config is False:
        return default
    val = config.get("highlights") or config.get("responsetype", {}).get("highlights")
    return val or default


@wrapper.config_reader
def get_paid_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    if config is False:
        return default
    val = config.get("paid") or config.get("responsetype", {}).get("paid")
    return val or default


@wrapper.config_reader
def get_messages_progress_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    if config is False:
        return default
    val = config.get("message") or config.get("responsetype", {}).get("message")
    return val or default


@wrapper.config_reader
def get_profile_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    if config is False:
        return default
    val = config.get("profile") or config.get("responsetype", {}).get("profile")
    return val or default


@wrapper.config_reader
def get_pinned_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    if config is False:
        return default
    val = config.get("pinned") or config.get("responsetype", {}).get("pinned")
    return val or default


@wrapper.config_reader
def get_streams_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]
    if config is False:
        return default
    val = config.get("streams") or config.get("responsetype", {}).get("streams")
    return val or default


@wrapper.config_reader
def get_spacereplacer(config=None):
    if config is False:
        return of_env.getattr("SPACE_REPLACER_DEFAULT")
    val = (
        config.get("space_replacer")
        or config.get("file_options", {}).get("space_replacer")
        or config.get("file_options", {}).get("space-replacer")
    )
    return val or of_env.getattr("SPACE_REPLACER_DEFAULT")


@wrapper.config_reader
def get_private_key(config=None):
    if not config:
        return None
    return config.get("private-key") or config.get("cdm_options", {}).get("private-key")


@wrapper.config_reader
def get_client_id(config=None):
    if not config:
        return None
    return config.get("client-id") or config.get("cdm_options", {}).get("client-id")


@wrapper.config_reader
def get_key_mode(config=None):
    if config is False:
        return of_env.getattr("KEY_DEFAULT")
    value = config.get("key-mode-default") or config.get("cdm_options", {}).get(
        "key-mode-default"
    )
    final_value = value if value is not None else of_env.getattr("KEY_DEFAULT")
    return (
        final_value.lower()
        if final_value and final_value.lower() in of_env.getattr("KEY_OPTIONS")
        else of_env.getattr("KEY_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config is False:
        return of_env.getattr("DYNAMIC_RULE_DEFAULT")
    value = config.get("dynamic-mode-default") or config.get(
        "advanced_options", {}
    ).get("dynamic-mode-default")
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
    val = config.get("auto_resume") or config.get("download_options", {}).get(
        "auto_resume"
    )
    if val is not None:
        return val
    legacy_val = config.get("partfileclean")
    if legacy_val is not None:
        return legacy_val is False
    return of_env.getattr("RESUME_DEFAULT")


@wrapper.config_reader
def get_download_semaphores(config=None):
    if config is False:
        return of_env.getattr("DOWNLOAD_SEM_DEFAULT")
    try:
        sem = config.get("download_sems") or config.get("performance_options", {}).get(
            "download_sems"
        )
        final_sem = sem if sem is not None else of_env.getattr("DOWNLOAD_SEM_DEFAULT")
        return int(final_sem)
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
    data = config.get("cache-mode") or config.get("advanced_options", {}).get(
        "cache-mode"
    )
    final_data = data if data is not None else of_env.getattr("CACHEDEFAULT")
    if final_data in {"sqlite", "json", "disabled"}:
        return final_data
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
    value = config.get("text_type_default") or config.get("file_options", {}).get(
        "text_type_default"
    )
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
    val = config.get("temp_dir") or config.get("advanced_options", {}).get("temp_dir")
    return val if val is not None else of_env.getattr("TEMP_FOLDER_DEFAULT")


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
        count = config.get("max_post_count") or config.get("download_options", {}).get(
            "max_post_count"
        )
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
    val = config.get("remove_hash_match") or config.get("advanced_options", {}).get(
        "remove_hash_match"
    )
    return val if val is not None else of_env.getattr("HASHED_DEFAULT")


@wrapper.config_reader
def get_block_ads(config=None):
    if config is False:
        return of_env.getattr("BLOCKED_ADS_DEFAULT")
    val = config.get("block_ads") or config.get("content_filter_options", {}).get(
        "block_ads"
    )
    return val if val is not None else of_env.getattr("BLOCKED_ADS_DEFAULT")


@wrapper.config_reader
def get_skip_unavailable_content(config=None):
    if config is False:
        return of_env.getattr("SKIP_UNAVAILABLE_DEFAULT")
    val = config.get("skip_unavailable_content") or config.get(
        "advanced_options", {}
    ).get("skip_unavailable_content")
    return val if val is not None else of_env.getattr("SKIP_UNAVAILABLE_DEFAULT")


@wrapper.config_reader
def get_verify_all_integrity(config=None):
    if config is False:
        return of_env.getattr("VERIFY_ALL_INTEGRITY")
    val = config.get("verify_all_integrity") or config.get("download_options", {}).get(
        "verify_all_integrity"
    )
    return val if val is not None else of_env.getattr("VERIFY_ALL_INTEGRITY")
