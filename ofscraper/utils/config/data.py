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

from ofscraper.utils.cache.safe_disk import SafeDisk, SafeJSONDisk
from humanfriendly import parse_size

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.utils.wrapper as wrapper

# auto_update_config rebuilds config.json from these getters and writes it
# back, so each must return what belongs in the file. Environment fallbacks
# that shouldn't be saved go in settings.merged_settings instead.
#
# _first, _value and _truthy_value are the lookups most getters share; the
# reference builder (scripts/reference/build_reference.py) reads their
# arguments to list each key's older names and environment default.


def strip_path_quotes(val):
    # Windows "Copy as path" wraps paths in double quotes, which then end up
    # literally inside the json string
    if isinstance(val, str):
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1].strip()
    return val


def _first(config, *paths):
    """
    The value at the first path that holds a truthy one, else the value at
    the last path: what ``config.get(a) or config.get(b) or ...`` gives. A
    path is a top-level key or "section.key". Later paths are only read when
    needed, so a broken section after a truthy value isn't touched.
    """
    val = None
    for path in paths:
        section, _, key = path.rpartition(".")
        val = config.get(section, {}).get(key) if section else config.get(key)
        if val:
            break
    return val


def _value(config, env_key, *paths):
    """_first(), falling back to the env_key default only when it's None, so
    a saved false, 0 or "" is kept"""
    if config is False:
        return of_env.getattr(env_key)
    val = _first(config, *paths)
    return val if val is not None else of_env.getattr(env_key)


def _truthy_value(config, env_key, *paths):
    """_first(), falling back to the env_key default when it's falsy"""
    if config is False:
        return of_env.getattr(env_key)
    return _first(config, *paths) or of_env.getattr(env_key)


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
        size = _value(
            config,
            "FILE_SIZE_MAX_DEFAULT",
            "file_size_max",
            "download_options.file_size_max",
            "download_options.file_size_limit",
            "content_filter_options.file_size_max",
        )
        return parse_size(str(size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_filesize_min(config=None):
    if config is False:
        return of_env.getattr("FILE_SIZE_MIN_DEFAULT")
    try:
        size = _value(
            config,
            "FILE_SIZE_MIN_DEFAULT",
            "file_size_min",
            "download_options.file_size_min",
            "content_filter_options.file_size_min",
        )
        return parse_size(str(size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_min_length(config=None):
    return _value(
        config,
        "MIN_LENGTH_DEFAULT",
        "length_min",
        "download_options.length_min",
        "content_filter_options.length_min",
    )


@wrapper.config_reader
def get_max_length(config=None):
    return _value(
        config,
        "MAX_LENGTH_DEFAULT",
        "length_max",
        "download_options.length_max",
        "content_filter_options.length_max",
    )


@wrapper.config_reader
def get_system_freesize(config=None):
    if config is False:
        return of_env.getattr("SYSTEM_FREEMIN_DEFAULT")
    try:
        size = _value(
            config,
            "SYSTEM_FREEMIN_DEFAULT",
            "system_free_min",
            "download_options.system_free_min",
        )
        return parse_size(str(size))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_dirformat(config=None):
    return _truthy_value(
        config, "DIR_FORMAT_DEFAULT", "dir_format", "file_options.dir_format"
    )


@wrapper.config_reader
def get_fileformat(config=None):
    return _truthy_value(
        config, "FILE_FORMAT_DEFAULT", "file_format", "file_options.file_format"
    )


@wrapper.config_reader
def get_textlength(config=None):
    if config is False:
        return of_env.getattr("TEXTLENGTH_DEFAULT")
    try:
        return int(
            _value(
                config, "TEXTLENGTH_DEFAULT", "textlength", "file_options.textlength"
            )
        )
    except (ValueError, TypeError):
        return of_env.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None):
    return _truthy_value(config, "DATE_DEFAULT", "date", "file_options.date")


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    return _value(
        config,
        "INFINITE_LOOP_DEFAULT",
        "infinite_loop_action_mode",
        "advanced_options.infinite_loop_action_mode",
    )


@wrapper.config_reader
def get_incremental_downloads(config=None):
    if config is False:
        return of_env.getattr("INCREMENTAL_DOWNLOADS_DEFAULT")
    # check each place for None, not falsiness, so a saved false is kept
    for val in (
        config.get("incremental_downloads"),
        config.get("advanced_options", {}).get("incremental_downloads"),
        config.get("advanced_options", {}).get("enable_auto_after"),
    ):
        if val is not None:
            return val
    return of_env.getattr("INCREMENTAL_DOWNLOADS_DEFAULT")


@wrapper.config_reader
def get_default_userlist(config=None):
    if config is False:
        return of_env.getattr("DEFAULT_USER_LIST") or []
    val = _first(config, "default_user_list", "advanced_options.default_user_list")
    return val or of_env.getattr("DEFAULT_USER_LIST") or []


@wrapper.config_reader
def get_default_blacklist(config=None):
    if config is False:
        return of_env.getattr("DEFAULT_BLACK_LIST") or []
    val = _first(config, "default_black_list", "advanced_options.default_black_list")
    return val or of_env.getattr("DEFAULT_BLACK_LIST") or []


@wrapper.config_reader
def get_logs_expire(config=None):
    if not config:
        return 0
    val = _first(config, "logs_expire_time", "advanced_options.logs_expire_time")
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
    return _value(
        config,
        "AFTER_ACTION_SCRIPT_DEFAULT",
        "after_action_script",
        "advanced_options.after_action_script",
        "script_options.after_action_script",
    )


@wrapper.config_reader
def get_post_script(config=None):
    return _value(
        config,
        "POST_SCRIPT_DEFAULT",
        "post_script",
        "advanced_options.post_script",
        "scripts.post_script",
        "script_options.post_script",
    )


@wrapper.config_reader
def get_naming_script(config=None):
    return _value(
        config,
        "NAMING_SCRIPT_DEFAULT",
        "naming_script",
        "advanced_options.naming_script",
        "scripts.naming_script",
        "script_options.naming_script",
    )


@wrapper.config_reader
def get_skip_download_script(config=None):
    return _value(
        config,
        "SKIP_DOWNLOAD_SCRIPT_DEFAULT",
        "skip_download_script",
        "advanced_options.skip_download_script",
        "scripts.skip_download_script",
        "script_options.skip_download_script",
    )


@wrapper.config_reader
def get_after_download_script(config=None):
    return _value(
        config,
        "AFTER_DOWNLOAD_SCRIPT_DEFAULT",
        "after_download_script",
        "advanced_options.after_download_script",
        "scripts.after_download_script",
        "script_options.after_download_script",
    )


@wrapper.config_reader
def get_env_files(config=None):
    # This must remain "safe" to avoid chicken-and-egg loops
    if config is False:
        return []
    val = _first(
        config,
        "env_files",
        "advanced_options.env_files",
        "scripts.env_files",
        "script_options.env_files",
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
        limit = _value(
            config,
            "DOWNLOAD_LIMIT_DEFAULT",
            "download_limit",
            "performance_options.download_limit",
        )
        return parse_size(str(limit))
    except (ValueError, TypeError):
        return 0


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config is False:
        return of_env.getattr("FFMPEG_DEFAULT")
    val = strip_path_quotes(_first(config, "ffmpeg", "binary_options.ffmpeg"))
    # "" is kept as-is so a config rewrite doesn't save OFSC_FFMPEG_DEFAULT
    # into the file; settings applies that fallback at runtime
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
    final_filter = _value(
        config,
        "FILTER_DEFAULT",
        "filter",
        "download_options.filter",
        "content_filter_options.filter",
    )
    if isinstance(final_filter, str):
        return [x.capitalize().strip() for x in final_filter.split(",")]
    elif isinstance(final_filter, list):
        return [x.capitalize() for x in final_filter]
    return []


@wrapper.config_reader
def responsetype(config=None):
    return _truthy_value(config, "RESPONSE_TYPE_DEFAULT", "responsetype")


@wrapper.config_reader
def get_timeline_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    if config is False:
        return default
    val = _first(
        config, "timeline", "post", "responsetype.timeline", "responsetype.post"
    )
    return val or default


@wrapper.config_reader
def get_post_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    if config is False:
        return default
    val = _first(
        config, "post", "timeline", "responsetype.post", "responsetype.timeline"
    )
    return val or default


@wrapper.config_reader
def get_archived_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    if config is False:
        return default
    return _first(config, "archived", "responsetype.archived") or default


@wrapper.config_reader
def get_stories_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    if config is False:
        return default
    return _first(config, "stories", "responsetype.stories") or default


@wrapper.config_reader
def get_highlights_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    if config is False:
        return default
    return _first(config, "highlights", "responsetype.highlights") or default


@wrapper.config_reader
def get_paid_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    if config is False:
        return default
    return _first(config, "paid", "responsetype.paid") or default


@wrapper.config_reader
def get_messages_progress_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    if config is False:
        return default
    return _first(config, "message", "responsetype.message") or default


@wrapper.config_reader
def get_profile_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    if config is False:
        return default
    return _first(config, "profile", "responsetype.profile") or default


@wrapper.config_reader
def get_pinned_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    if config is False:
        return default
    return _first(config, "pinned", "responsetype.pinned") or default


@wrapper.config_reader
def get_streams_responsetype(config=None):
    default = of_env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]
    if config is False:
        return default
    return _first(config, "streams", "responsetype.streams") or default


@wrapper.config_reader
def get_spacereplacer(config=None):
    return _truthy_value(
        config,
        "SPACE_REPLACER_DEFAULT",
        "space_replacer",
        "file_options.space_replacer",
        "file_options.space-replacer",
    )


@wrapper.config_reader
def get_private_key(config=None):
    if not config:
        return None
    return strip_path_quotes(_first(config, "private-key", "cdm_options.private-key"))


@wrapper.config_reader
def get_client_id(config=None):
    if not config:
        return None
    return strip_path_quotes(_first(config, "client-id", "cdm_options.client-id"))


@wrapper.config_reader
def get_key_mode(config=None):
    if config is False:
        return of_env.getattr("KEY_DEFAULT")
    final_value = _value(
        config, "KEY_DEFAULT", "key-mode-default", "cdm_options.key-mode-default"
    )
    return (
        final_value.lower()
        if final_value and final_value.lower() in of_env.getattr("KEY_OPTIONS")
        else of_env.getattr("KEY_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config is False:
        return of_env.getattr("DYNAMIC_RULE_DEFAULT")
    final_value = _value(
        config,
        "DYNAMIC_RULE_DEFAULT",
        "dynamic-mode-default",
        "advanced_options.dynamic-mode-default",
    )
    return (
        final_value.lower()
        if final_value and final_value.lower() in of_env.getattr("DYNAMIC_OPTIONS_ALL")
        else of_env.getattr("DYNAMIC_RULE_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic_configured(config=None):
    # the raw value, before get_dynamic() checks it; not written to the file
    if config is False:
        return None
    return _first(
        config, "dynamic-mode-default", "advanced_options.dynamic-mode-default"
    )


@wrapper.config_reader
def get_part_file_clean(config=None):
    if config is False:
        return of_env.getattr("RESUME_DEFAULT")
    val = _first(config, "auto_resume", "download_options.auto_resume")
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
        final_sem = int(
            _value(
                config,
                "DOWNLOAD_SEM_DEFAULT",
                "download_sems",
                "performance_options.download_sems",
            )
        )
        # the download pool needs at least one worker
        if final_sem < 1:
            return int(of_env.getattr("DOWNLOAD_SEM_DEFAULT"))
        return final_sem
    except (ValueError, TypeError):
        return int(of_env.getattr("DOWNLOAD_SEM_DEFAULT"))


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    return _value(
        config, "PROGRESS_DEFAULT", "downloadbars", "advanced_options.downloadbars"
    )


@wrapper.config_reader
def get_cache_mode(config=None):
    # diskcache's disks, reading only plain data back (CVE-2025-69872)
    if cache_mode_helper(config=config) == "json":
        return SafeJSONDisk
    else:
        return SafeDisk


def cache_mode_helper(config=None):
    if config is False:
        return of_env.getattr("CACHEDEFAULT")
    if config is None:
        config = config_file.open_config()
    final_data = _value(
        config, "CACHEDEFAULT", "cache-mode", "advanced_options.cache-mode"
    )
    if final_data in {"sqlite", "json", "disabled", "api_disabled"}:
        return final_data
    else:
        return of_env.getattr("CACHEDEFAULT")


@wrapper.config_reader
def get_rotate_logs(config=None):
    return _value(
        config, "ROTATE_DEFAULT", "rotate_logs", "advanced_options.rotate_logs"
    )


@wrapper.config_reader
def get_sanitizeDB(config=None):
    return _value(
        config, "SANITIZE_DB_DEFAULT", "sanitize_text", "advanced_options.sanitize_text"
    )


@wrapper.config_reader
def get_textType(config=None):
    if config is False:
        return of_env.getattr("TEXT_TYPE_DEFAULT")
    final_value = _value(
        config,
        "TEXT_TYPE_DEFAULT",
        "text_type_default",
        "file_options.text_type_default",
    )
    return (
        final_value
        if final_value in {"letter", "word"}
        else of_env.getattr("TEXT_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_TempDir(config=None):
    if config is False:
        return of_env.getattr("TEMP_FOLDER_DEFAULT")
    val = _first(config, "temp_dir", "advanced_options.temp_dir")
    return strip_path_quotes(val) if val is not None else of_env.getattr("TEMP_FOLDER_DEFAULT")


@wrapper.config_reader
def get_filename_collision(config=None):
    return _value(
        config,
        "FILENAME_COLLISION_DEFAULT",
        "filename_collision",
        "file_options.filename_collision",
    )


@wrapper.config_reader
def get_truncation(config=None):
    return _value(
        config,
        "TRUNCATION_DEFAULT",
        "truncation_default",
        "file_options.truncation_default",
    )


@wrapper.config_reader
def get_max_post_count(config=None):
    if config is False:
        return of_env.getattr("MAX_COUNT_DEFAULT")
    try:
        return int(
            _value(
                config,
                "MAX_COUNT_DEFAULT",
                "max_post_count",
                "download_options.max_post_count",
            )
        )
    except (ValueError, TypeError):
        return of_env.getattr("MAX_COUNT_DEFAULT")


@wrapper.config_reader
def get_hash(config=None):
    return _value(
        config,
        "HASHED_DEFAULT",
        "remove_hash_match",
        "advanced_options.remove_hash_match",
    )


@wrapper.config_reader
def get_block_ads(config=None):
    return _value(
        config, "BLOCKED_ADS_DEFAULT", "block_ads", "content_filter_options.block_ads"
    )


@wrapper.config_reader
def get_skip_unavailable_content(config=None):
    return _value(
        config,
        "SKIP_UNAVAILABLE_DEFAULT",
        "skip_unavailable_content",
        "advanced_options.skip_unavailable_content",
    )


@wrapper.config_reader
def get_verify_all_integrity(config=None):
    return _value(
        config,
        "VERIFY_ALL_INTEGRITY",
        "verify_all_integrity",
        "download_options.verify_all_integrity",
    )
