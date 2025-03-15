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

import ofscraper.const.constants as constants
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.utils.wrapper as wrapper
import ofscraper.utils.constants as constants_attr


@wrapper.config_reader
def get_main_profile(config=None):
    if config is False:
        return constants.PROFILE_DEFAULT
    return config.get(
        constants_attr.getattr("mainProfile"), constants_attr.getattr("PROFILE_DEFAULT")
    ) or constants_attr.getattr("PROFILE_DEFAULT")


@wrapper.config_reader
def get_filesize_max(config=None, mediatype=None):
    if config is False:
        return constants.FILE_SIZE_MAX_DEFAULT
    try:
        if config.get("file_size_max") is not None:
            size = config.get("file_size_max")

        elif (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("file_size_max")
        ):
            size = (
                config.get("overwrites", {})
                .get((mediatype or "").lower(), {})
                .get("file_size_max")
            )
        elif config.get("download_options", {}).get("file_size_max"):
            size = config.get("download_options", {}).get("file_size_max")

        elif config.get("download_options", {}).get("file_size_limit"):
            size = config.get("download_options", {}).get("file_size_limit")
        elif config.get("content_filter_options", {}).get("file_size_max"):
            size = config.get("content_filter_options", {}).get("file_size_max")
        return parse_size(
            str(
                size
                if size is not None
                else constants_attr.getattr("FILE_SIZE_MAX_DEFAULT")
            )
        )
    except:
        return 0


@wrapper.config_reader
def get_filesize_min(config=None, mediatype=None):
    if config is False:
        return constants.FILE_SIZE_MIN_DEFAULT
    try:
        size = None
        if (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("file_size_min")
        ):
            size = (
                config.get("overwrites", {})
                .get((mediatype or "").lower(), {})
                .get("file_size_min")
            )
        elif config.get("file_size_min") is not None:
            size = config.get("file_size_min")

        elif config.get("download_options", {}).get("file_size_min"):
            size = config.get("download_options", {}).get("file_size_min")
        elif config.get("content_filter_options", {}).get("file_size_min"):
            size = config.get("content_filter_options", {}).get("file_size_min")
        return parse_size(
            str(
                size
                if size is not None
                else constants_attr.getattr("FILE_SIZE_MIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_min_length(config=None, mediatype=None):
    if config is False:
        return constants.MIN_LENGTH_DEFAULT

    elif (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("length_min")
    ):
        return (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("length_min")
        )
    elif "length_min" in config:
        return config.get("length_min", {})

    elif config.get("download_options", {}).get("length_min"):
        return config.get("download_options", {}).get("length_min")
    elif config.get("content_filter_options", {}).get("length_min"):
        return config.get("content_filter_options", {}).get("length_min")


@wrapper.config_reader
def get_max_length(config=None, mediatype=None):
    if config is False:
        return constants.MAX_LENGTH_DEFAULT

    elif (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("length_max")
    ):
        return (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("length_max")
        )
    elif "length_min" in config:
        return config.get("length_max", {})

    elif config.get("download_options", {}).get("length_max"):
        return config.get("download_options", {}).get("length_max")
    elif config.get("content_filter_options", {}).get("length_max"):
        return config.get("content_filter_options", {}).get("length_max")


@wrapper.config_reader
def get_system_freesize(config=None, mediatype=None):
    if config is False:
        return constants.SYSTEM_FREEMIN_DEFAULT
    try:
        return parse_size(
            str(
                config.get("overwrites", {})
                .get((mediatype or "").lower(), {})
                .get("system_free_min")
                or config.get("system_free_min")
                or config.get("download_options", {}).get("system_free_min")
                or constants_attr.getattr("SYSTEM_FREEMIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_dirformat(config=None, mediatype=None):
    if config is False:
        return constants.DIR_FORMAT_DEFAULT
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("dir_format")
        or config.get("dir_format")
        or config.get("file_options", {}).get("dir_format")
        or constants_attr.getattr("DIR_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_fileformat(config=None, mediatype=None):
    if config is False:
        return constants.FILE_FORMAT_DEFAULT
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("file_format")
        or config.get("file_format")
        or config.get("file_options", {}).get("file_format")
        or constants_attr.getattr("FILE_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_textlength(config=None, mediatype=None):
    if config is False:
        return constants.TEXTLENGTH_DEFAULT
    try:
        return int(
            config.get("overwrites", {}).get(f"{mediatype}", {}).get("textlength")
            or config.get("textlength")
            or config.get("file_options", {}).get("textlength")
        ) or constants_attr.getattr("TEXTLENGTH_DEFAULT")
    except:
        return constants_attr.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None, mediatype=None):
    if config is False:
        return constants.DATE_DEFAULT
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("date")
        or config.get("date")
        or config.get("file_options", {}).get("date")
        or constants_attr.getattr("DATE_DEFAULT")
    )


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    if config is False:
        return constants.INFINITE_LOOP_DEFAULT
    val = (
        config.get("infinite_loop_action_mode")
        if config.get("infinite_loop_action_mode") is not None
        else config.get("advanced_options", {}).get("infinite_loop_action_mode")
    )
    return val if val is not None else constants_attr.getattr("INFINITE_LOOP_DEFAULT")


@wrapper.config_reader
def get_enable_after(config=None):
    if config is False:
        return constants.ENABLE_AUTO_AFTER_DEFAULT
    val = not config.get("disable_auto_after")
    val = (
        not config.get("advanced_options", {}).get("disable_auto_after")
        if val is None
        else val
    )
    val = config.get("enable_auto_after") if val is None else val
    val = (
        config.get("advanced_options", {}).get("enable_auto_after")
        if val is None
        else val
    )

    return (
        val if val is not None else constants_attr.getattr("ENABLE_AUTO_AFTER_DEFAULT")
    )


@wrapper.config_reader
def get_default_userlist(config=None):
    if config is False:
        return constants.DEFAULT_USER_LIST
    val = (
        config.get("default_user_list")
        if not any(x == config.get("default_user_list") for x in [None, ""])
        else config.get("advanced_options", {}).get("default_user_list")
    )
    return (
        val
        if not any(x == val for x in [None, ""])
        else constants_attr.getattr("DEFAULT_USER_LIST")
    )


@wrapper.config_reader
def get_post_download_script(config=None):
    if config is False:
        return constants.POST_DOWNLOAD_SCRIPT_DEFAULT
    val = None
    if config.get("post_download_script") is not None:
        val = config.get("post_download_script")
    elif config.get("advanced_options", {}).get("post_download_script") is not None:
        val = config.get("advanced_options", {}).get("post_download_script")
    elif config.get("script_options", {}).get("post_download_script") is not None:
        val = config.get("script_options", {}).get("post_download_script")
    return (
        val
        if val is not None
        else constants_attr.getattr("POST_DOWNLOAD_SCRIPT_DEFAULT")
    )


@wrapper.config_reader
def get_post_script(config=None):
    if config is False:
        return constants.POST_SCRIPT_DEFAULT
    val = None
    if config.get("post_script") is not None:
        val = config.get("post_script")
    elif config.get("advanced_options", {}).get("post_script") is not None:
        val = config.get("advanced_options", {}).get("post_script")
    elif config.get("scripts", {}).get("post_script") is not None:
        val = config.get("scripts", {}).get("post_script")
    elif config.get("script_options", {}).get("post_script") is not None:
        val = config.get("script_options", {}).get("post_script")
    return val if val is not None else constants_attr.getattr("POST_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_default_blacklist(config=None):
    if config is False:
        return constants.DEFAULT_BLACK_LIST
    val = (
        config.get("default_black_list")
        if not any(x == config.get("default_black_list") for x in [None, ""])
        else config.get("advanced_options", {}).get("default_black_list")
    )
    return (
        val
        if not any(x == val for x in [None, ""])
        else constants_attr.getattr("DEFAULT_BLACK_LIST")
    )


@wrapper.config_reader
def get_allow_code_execution(config=None):
    if config is False:
        return constants.CODE_EXECUTION_DEFAULT
    val = (
        config.get("code-execution")
        if config.get("code-execution") is not None
        else config.get("advanced_options", {}).get("code-execution")
    )
    return val if val is not None else constants_attr.getattr("CODE_EXECUTION_DEFAULT")


@wrapper.config_reader
def get_metadata(config=None):
    if config is False:
        return constants.METADATA_DEFAULT
    return config.get("metadata", constants_attr.getattr("METADATA_DEFAULT"))


@wrapper.config_reader
def get_download_limit(config=None, mediatype=None):
    if config is False:
        return constants.DOWNLOAD_LIMIT_DEFAULT
    try:
        return parse_size(
            str(
                config.get("overwrites", {})
                .get((mediatype or "").lower(), {})
                .get("download_limit")
                or config.get(
                    "download_limit",
                )
                or config.get("performance_options", {}).get("download_limit")
                or constants_attr.getattr("DOWNLOAD_LIMIT_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config is False:
        return constants.FFMPEG_DEFAULT
    return (
        config.get("ffmpeg")
        or config.get("binary_options", {}).get("ffmpeg")
        or constants_attr.getattr("FFMPEG_DEFAULT")
    )


@wrapper.config_reader
def get_discord(config=None):
    if config is False:
        return constants.DISCORD_DEFAULT
    return config.get("discord", constants_attr.getattr("DISCORD_DEFAULT")) or ""


@wrapper.config_reader
def get_filter(config=None):
    if config is False:
        return constants.FILTER_DEFAULT
    filter = (
        config.get("filter")
        or config.get("download_options", {}).get("filter")
        or config.get("content_filter_options", {}).get("filter")
        or constants_attr.getattr("FILTER_DEFAULT")
    )
    if isinstance(filter, str):
        return list(map(lambda x: x.capitalize().strip(), filter.split(",")))
    elif isinstance(filter, list):
        return list(map(lambda x: x.capitalize(), filter))


@wrapper.config_reader
def responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        or config.get("responsetype", {})
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_timeline_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["timeline"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("post")
        or config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("timeline")
        or config.get("timeline")
        or config.get("post")
        or config.get("responsetype", {}).get("timeline")
        or config.get("responsetype", {}).get("post")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_post_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["timeline"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("post")
        or config.get("overwrites", {}).get((mediatype or "").lower(), {})
        or config.get("post")
        or config.get("timeline").get("responsetype", {}).get("timeline")
        or config.get("responsetype", {}).get("post")
        or config.get("responsetype", {}).get("timeline")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_archived_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["archived"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("archived")
        or config.get("archived")
        or config.get("responsetype", {}).get("archived")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    )


@wrapper.config_reader
def get_stories_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["stories"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("stories")
        or config.get("stories")
        or config.get("responsetype", {}).get("stories")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    )


@wrapper.config_reader
def get_highlights_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["highlights"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("highlights")
        or config.get("highlights")
        or config.get("responsetype", {}).get("highlights")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    )


@wrapper.config_reader
def get_paid_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["paid"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("paid")
        or config.get("paid")
        or config.get("responsetype", {}).get("paid")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    )


@wrapper.config_reader
def get_messages_progress_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["message"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("message")
        or config.get("message")
        or config.get("responsetype", {}).get("message")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    )


@wrapper.config_reader
def get_profile_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["profile"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("profile")
        or config.get("profile")
        or config.get("responsetype", {}).get("profile")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    )


@wrapper.config_reader
def get_pinned_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["pinned"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("pinned")
        or config.get("pinned")
        or config.get("responsetype", {}).get("pinned")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    )


@wrapper.config_reader
def get_streams_responsetype(config=None, mediatype=None):
    if config is False:
        return constants.RESPONSE_TYPE_DEFAULT["streams"]
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("streams")
        or config.get("streams")
        or config.get("responsetype", {}).get("streams")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["streams"]
    )


@wrapper.config_reader
def get_spacereplacer(config=None, mediatype=None):
    if config is False:
        return constants.SPACE_REPLACER_DEFAULT
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("space_replacer")
        or config.get("space_replacer")
        or config.get("file_options", {}).get("space_replacer")
        or config.get("file_options", {}).get("space-replacer")
        or constants_attr.getattr("SPACE_REPLACER_DEFAULT")
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
        return constants.KEY_DEFAULT
    value = config.get("key-mode-default") or config.get("cdm_options", {}).get(
        "key-mode-default"
    )

    return (
        value.lower()
        if value and value.lower() in set(constants_attr.getattr("KEY_OPTIONS"))
        else constants_attr.getattr("KEY_DEFAULT")
    )


@wrapper.config_reader
def get_keydb_api(config=None):
    if config is False:
        return constants.KEYDB_DEFAULT
    return (
        config.get("keydb_api")
        or config.get("cdm_options", {}).get("keydb_api")
        or constants_attr.getattr("KEYDB_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config is False:
        return constants.DYNAMIC_DEFAULT
    value = config.get("dynamic-mode-default") or config.get(
        "advanced_options", {}
    ).get("dynamic-mode-default")
    return (
        value.lower()
        if value and value.lower() in set(constants_attr.getattr("DYNAMIC_OPTIONS_ALL"))
        else constants_attr.getattr("DYNAMIC_RULE_DEFAULT")
    )


@wrapper.config_reader
def get_part_file_clean(config=None, mediatype=None):
    if config is False:
        return constants.RESUME_DEFAULT
    if (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("auto_resume")
    ):
        return (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("auto_resume")
        )
    elif config.get("auto_resume"):
        return config.get("auto_resume")
    elif config.get("download_options", {}).get("auto_resume") is not None:
        return config.get("download_options", {}).get("auto_resume")
    elif config.get("partfileclean") is not None:
        return config.get("partfileclean") is False
    return constants_attr.getattr("RESUME_DEFAULT")


@wrapper.config_reader
def get_backend(config=None):
    if config is False:
        return constants.BACKEND_DEFAULT
    return (
        config.get("backend")
        or config.get("advanced_options", {}).get("backend")
        or constants_attr.getattr("BACKEND_DEFAULT")
    )


@wrapper.config_reader
def get_download_semaphores(config=None):
    if config is False:
        return constants.DOWNLOAD_SEM_DEFAULT
    sem = (
        config.get("download_sems")
        or config.get("performance_options", {}).get("download_sems")
        or constants_attr.getattr("DOWNLOAD_SEM_DEFAULT")
    )
    try:
        sem = int(sem)
    except ValueError:
        sem = int(constants_attr.getattr("DOWNLOAD_SEM_DEFAULT"))
    return sem


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    if config is False:
        return constants.PROGRESS_DEFAULT
    val = (
        config.get("downloadbars")
        if config.get("downloadbars") is not None
        else config.get("advanced_options", {}).get("downloadbars")
    )
    return val if val is not None else constants_attr.getattr("PROGRESS_DEFAULT")


@wrapper.config_reader
def get_cache_mode(config=None):
    if cache_mode_helper(config=config) == "sqlite":
        return Disk
    else:
        return JSONDisk


def cache_mode_helper(config=None):
    if config is False:
        return constants.CACHEDEFAULT
    if config is None:
        config = config_file.open_config()
    data = (
        config.get("cache-mode")
        or config.get("advanced_options", {}).get("cache-mode")
        or constants_attr.getattr("CACHEDEFAULT")
    )
    if data == "disabled":
        return data
    if data in [constants_attr.getattr("CACHEDEFAULT"), "json"]:
        return data
    else:
        return constants_attr.getattr("CACHEDEFAULT")


@wrapper.config_reader
def get_appendlog(config=None):
    if config is False:
        return constants.APPEND_DEFAULT
    value = (
        config.get("appendlog")
        if config.get("appendlog") is not None
        else config.get("advanced_options", {}).get("appendlog")
    )
    return value if value is not None else constants_attr.getattr("APPEND_DEFAULT")


@wrapper.config_reader
def get_sanitizeDB(config=None):
    if config is False:
        return constants.SANITIZE_DB_DEFAULT
    val = (
        config.get("sanitize_text")
        if config.get("sanitize_text") is not None
        else config.get("advanced_options", {}).get("sanitize_text")
    )
    return val if val is not None else constants_attr.getattr("SANITIZE_DB_DEFAULT")


@wrapper.config_reader
def get_textType(config=None, mediatype=None):
    if config is False:
        return constants.TEXT_TYPE_DEFAULT
    value = (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("text_type_default")
        or config.get("text_type_default")
        or config.get("file_options", {}).get("text_type_default")
    )
    return (
        value
        if value in ["letter", "word"]
        else constants_attr.getattr("TEXT_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_TempDir(config=None, mediatype=None):
    if config is False:
        return constants.TEMP_FOLDER_DEFAULT
    return (
        config.get("overwrites", {}).get((mediatype or "").lower(), {}).get("temp_dir")
        or config.get("temp_dir")
        or config.get("advanced_options", {}).get("temp_dir")
        or constants_attr.getattr("TEMP_FOLDER_DEFAULT")
    )


@wrapper.config_reader
def get_truncation(config=None, mediatype=None):
    val = None
    if config is False:
        return constants.TRUNCATION_DEFAULT

    if config.get("overwrites", {}).get(f"{mediatype}", {}).get("truncation_default"):
        val = (
            config.get("overwrites", {})
            .get(f"{mediatype}", {})
            .get("truncation_default")
        )
    elif config.get("truncation_default"):
        val = config.get("truncation_default")
    elif config.get("file_options", {}).get("truncation_default"):
        val = config.get("file_options", {}).get("truncation_default")
    return val if val is not None else constants_attr.getattr("TRUNCATION_DEFAULT")


@wrapper.config_reader
def get_audios_overwrites(config=None):
    if config is False:
        return constants.EMPTY_MEDIA_DEFAULT
    return config.get("overwrites", {}).get("audios") or constants_attr.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_videos_overwrites(config=None):
    if config is False:
        return constants.EMPTY_MEDIA_DEFAULT
    return config.get("overwrites", {}).get("videos") or constants_attr.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_images_overwrites(config=None):
    if config is False:
        return constants.EMPTY_MEDIA_DEFAULT
    return config.get("overwrites", {}).get("images") or constants_attr.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_text_overwrites(config=None):
    if config is False:
        return constants.EMPTY_MEDIA_DEFAULT
    return config.get("overwrites", {}).get("text") or constants_attr.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_max_post_count(config=None):
    if config is False:
        return constants.MAX_COUNT_DEFAULT
    try:
        if config.get("max_post_count") is not None:
            return int(config.get("max_post_count"))
        elif config.get("download_options", {}).get("max_post_count") is not None:
            return int(config.get("download_options", {}).get("max_post_count"))
        return int(constants_attr.getattr("MAX_COUNT_DEFAULT"))
    except Exception:
        return constants_attr.getattr("MAX_COUNT_DEFAULT")


@wrapper.config_reader
def get_hash(config=None, mediatype=None):
    if config is False:
        return constants.HASHED_DEFAULT
    elif (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("remove_hash_match")
    ):
        return (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("remove_hash_match")
        )
    elif "remove_hash_match" in config:
        return config.get("remove_hash_match")
    elif "remove_hash_match" in config.get("advanced_options", {}):
        return config.get("advanced_options", {}).get("remove_hash_match")
    return constants_attr.getattr("HASHED_DEFAULT")


@wrapper.config_reader
def get_block_ads(config=None, mediatype=None):
    if config is False:
        return constants.BLOCKED_ADS_DEFAULT
    elif (
        config.get("overwrites", {}).get((mediatype or "").lower(), {}).get("block_ads")
    ):
        return (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("block_ads")
        )
    elif (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("content_filter_options", {})
        .get("block_ads")
    ):
        return (
            config.get("overwrites", {})
            .get((mediatype or "").lower(), {})
            .get("content_filter_options", {})
            .get("block_ads")
        )
    elif "block_ads" in config:
        return config.get("block_ads")
    elif "block_ads" in config.get("content_filter_options", {}):
        return config.get("content_filter_options", {}).get("block_ads")
    return constants_attr.getattr("BLOCKED_ADS_DEFAULT")
