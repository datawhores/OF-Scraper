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

import ofscraper.utils.env.env as env
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.utils.wrapper as wrapper
import ofscraper.utils.const as const


@wrapper.config_reader
def get_main_profile(config=None):
    if config is False:
        return env.getattr("")
    return config.get(
        env.getattr("mainProfile"), env.getattr("PROFILE_DEFAULT")
    ) or env.getattr("PROFILE_DEFAULT")


@wrapper.config_reader
def get_filesize_max(config=None, mediatype=None):
    if config is False:
        return env.getattr("FILE_SIZE_MAX_DEFAULT")
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
                else env.getattr("FILE_SIZE_MAX_DEFAULT")
            )
        )
    except:
        return 0


@wrapper.config_reader
def get_filesize_min(config=None, mediatype=None):
    if config is False:
        return env.getattr("FILE_SIZE_MIN_DEFAULT")
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
                else env.getattr("FILE_SIZE_MIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_min_length(config=None, mediatype=None):
    if config is False:
        return env.getattr("MIN_LENGTH_DEFAULT")

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
        return env.getattr("MAX_LENGTH_DEFAULT")

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
        return env.getattr("SYSTEM_FREEMIN_DEFAULT")
    try:
        return parse_size(
            str(
                config.get("overwrites", {})
                .get((mediatype or "").lower(), {})
                .get("system_free_min")
                or config.get("system_free_min")
                or config.get("download_options", {}).get("system_free_min")
                or env.getattr("SYSTEM_FREEMIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_dirformat(config=None, mediatype=None):
    if config is False:
        return env.getattr("DIR_FORMAT_DEFAULT")
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("dir_format")
        or config.get("dir_format")
        or config.get("file_options", {}).get("dir_format")
        or env.getattr("DIR_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_fileformat(config=None, mediatype=None):
    if config is False:
        return env.getattr("FILE_FORMAT_DEFAULT")
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("file_format")
        or config.get("file_format")
        or config.get("file_options", {}).get("file_format")
        or env.getattr("FILE_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_textlength(config=None, mediatype=None):
    if config is False:
        return env.getattr("TEXTLENGTH_DEFAULT")
    try:
        return int(
            config.get("overwrites", {}).get(f"{mediatype}", {}).get("textlength")
            or config.get("textlength")
            or config.get("file_options", {}).get("textlength")
        ) or env.getattr("TEXTLENGTH_DEFAULT")
    except:
        return env.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None, mediatype=None):
    if config is False:
        return env.getattr("DATE_DEFAULT")
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("date")
        or config.get("date")
        or config.get("file_options", {}).get("date")
        or env.getattr("DATE_DEFAULT")
    )


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    if config is False:
        return env.getattr("INFINITE_LOOP_DEFAULT")
    val = (
        config.get("infinite_loop_action_mode")
        if config.get("infinite_loop_action_mode") is not None
        else config.get("advanced_options", {}).get("infinite_loop_action_mode")
    )
    return val if val is not None else env.getattr("INFINITE_LOOP_DEFAULT")


@wrapper.config_reader
def get_enable_after(config=None):
    if config is False:
        return env.getattr("ENABLE_AUTO_AFTER_DEFAULT")
    val = config.get("enable_auto_after")
    val = (
        config.get("advanced_options", {}).get("enable_auto_after")
        if val is None
        else val
    )

    return (
        val if val is not None else env.getattr("ENABLE_AUTO_AFTER_DEFAULT")
    )


@wrapper.config_reader
def get_default_userlist(config=None):
    if config is False:
        return env.getattr("DEFAULT_USER_LIST")
    val = (
        config.get("default_user_list")
        if not any(x == config.get("default_user_list") for x in [None, ""])
        else config.get("advanced_options", {}).get("default_user_list")
    )
    return (
        val
        if not any(x == val for x in [None, ""])
        else env.getattr("DEFAULT_USER_LIST")
    )


@wrapper.config_reader
def get_logs_expire(config=None):
   if not config:
       return None
   return(
        config.get("logs_expire_time")
        if not any(x == config.get("logs_expire_time") for x in [None, ""])
        else config.get("advanced_options", {}).get("logs_expire_time")
    )

@wrapper.config_reader
def get_ssl_validation(config=None):
    val = (
        config.get("ssl_validation")
        if not any(x == config.get("ssl_validation") for x in [None, ""])
        else config.get("advanced_options", {}).get("ssl_validation")
    )
    if val is None:
        return False
    else:
        return val
@wrapper.config_reader
def get_post_download_script(config=None):
    if config is False:
        return env.getattr("POST_DOWNLOAD_SCRIPT_DEFAULT")
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
        else env.getattr("POST_DOWNLOAD_SCRIPT_DEFAULT")
    )


@wrapper.config_reader
def get_post_script(config=None):
    if config is False:
        return env.getattr("POST_SCRIPT_DEFAULT")
    val = None
    if config.get("post_script") is not None:
        val = config.get("post_script")
    elif config.get("advanced_options", {}).get("post_script") is not None:
        val = config.get("advanced_options", {}).get("post_script")
    elif config.get("scripts", {}).get("post_script") is not None:
        val = config.get("scripts", {}).get("post_script")
    elif config.get("script_options", {}).get("post_script") is not None:
        val = config.get("script_options", {}).get("post_script")
    return val if val is not None else env.getattr("POST_SCRIPT_DEFAULT")


@wrapper.config_reader
def get_default_blacklist(config=None):
    if config is False:
        return env.getattr("DEFAULT_BLACK_LIST")
    val = (
        config.get("default_black_list")
        if not any(x == config.get("default_black_list") for x in [None, ""])
        else config.get("advanced_options", {}).get("default_black_list")
    )
    return (
        val
        if not any(x == val for x in [None, ""])
        else env.getattr("DEFAULT_BLACK_LIST")
    )


@wrapper.config_reader
def get_allow_code_execution(config=None):
    if config is False:
        return env.getattr("CODE_EXECUTION_DEFAULT")
    val = (
        config.get("code-execution")
        if config.get("code-execution") is not None
        else config.get("advanced_options", {}).get("code-execution")
    )
    return val if val is not None else env.getattr("CODE_EXECUTION_DEFAULT")


@wrapper.config_reader
def get_metadata(config=None):
    if config is False:
        return env.getattr("METADATA_DEFAULT")
    return config.get("metadata", env.getattr("METADATA_DEFAULT"))


@wrapper.config_reader
def get_download_limit(config=None, mediatype=None):
    if config is False:
        return env.getattr("DOWNLOAD_LIMIT_DEFAULT")
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
                or env.getattr("DOWNLOAD_LIMIT_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config is False:
        return env.getattr("FFMPEG_DEFAULT")
    return (
        config.get("ffmpeg")
        or config.get("binary_options", {}).get("ffmpeg")
        or env.getattr("FFMPEG_DEFAULT")
    )


@wrapper.config_reader
def get_discord(config=None):
    if config is False:
        return env.getattr("DISCORD_DEFAULT")
    return config.get("discord", env.getattr("DISCORD_DEFAULT")) or ""


@wrapper.config_reader
def get_filter(config=None):
    if config is False:
        return env.getattr("FILTER_DEFAULT")
    filter = (
        config.get("filter")
        or config.get("download_options", {}).get("filter")
        or config.get("content_filter_options", {}).get("filter")
        or env.getattr("FILTER_DEFAULT")
    )
    if isinstance(filter, str):
        return list(map(lambda x: x.capitalize().strip(), filter.split(",")))
    elif isinstance(filter, list):
        return list(map(lambda x: x.capitalize(), filter))


@wrapper.config_reader
def responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        or config.get("responsetype", {})
        or env.getattr("RESPONSE_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_timeline_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['timeline']")
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
        or env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_post_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['timeline']")
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
        or env.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_archived_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['archived']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("archived")
        or config.get("archived")
        or config.get("responsetype", {}).get("archived")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    )


@wrapper.config_reader
def get_stories_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['stories']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("stories")
        or config.get("stories")
        or config.get("responsetype", {}).get("stories")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    )


@wrapper.config_reader
def get_highlights_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['highlights']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("highlights")
        or config.get("highlights")
        or config.get("responsetype", {}).get("highlights")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    )


@wrapper.config_reader
def get_paid_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['paid']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("paid")
        or config.get("paid")
        or config.get("responsetype", {}).get("paid")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    )


@wrapper.config_reader
def get_messages_progress_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['message']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("message")
        or config.get("message")
        or config.get("responsetype", {}).get("message")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    )


@wrapper.config_reader
def get_profile_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['profile']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("profile")
        or config.get("profile")
        or config.get("responsetype", {}).get("profile")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    )


@wrapper.config_reader
def get_pinned_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['pinned']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("pinned")
        or config.get("pinned")
        or config.get("responsetype", {}).get("pinned")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    )


@wrapper.config_reader
def get_streams_responsetype(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESPONSE_TYPE_DEFAULT['streams']")
    return (
        config.get("overwrites", {})
        .get((mediatype or "").lower(), {})
        .get("responsetype", {})
        .get("streams")
        or config.get("streams")
        or config.get("responsetype", {}).get("streams")
        or env.getattr("RESPONSE_TYPE_DEFAULT")["streams"]
    )


@wrapper.config_reader
def get_spacereplacer(config=None, mediatype=None):
    if config is False:
        return env.getattr("SPACE_REPLACER_DEFAULT")
    return (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("space_replacer")
        or config.get("space_replacer")
        or config.get("file_options", {}).get("space_replacer")
        or config.get("file_options", {}).get("space-replacer")
        or env.getattr("SPACE_REPLACER_DEFAULT")
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
        return env.getattr("KEY_DEFAULT")
    value = config.get("key-mode-default") or config.get("cdm_options", {}).get(
        "key-mode-default"
    )

    return (
        value.lower()
        if value and value.lower() in set(const.KEY_OPTIONS)
        else env.getattr("KEY_DEFAULT")
    )

@wrapper.config_reader
def get_dynamic(config=None):
    if config is False:
        return env.getattr("DYNAMIC_RULE_DEFAULT")
    value = config.get("dynamic-mode-default") or config.get(
        "advanced_options", {}
    ).get("dynamic-mode-default")
    return (
        value.lower()
        if value and value.lower() in set(env.getattr("DYNAMIC_OPTIONS_ALL"))
        else env.getattr("DYNAMIC_RULE_DEFAULT")
    )


@wrapper.config_reader
def get_part_file_clean(config=None, mediatype=None):
    if config is False:
        return env.getattr("RESUME_DEFAULT")
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
    return env.getattr("RESUME_DEFAULT")

@wrapper.config_reader
def get_download_semaphores(config=None):
    if config is False:
        return env.getattr("DOWNLOAD_SEM_DEFAULT")
    sem = (
        config.get("download_sems")
        or config.get("performance_options", {}).get("download_sems")
        or env.getattr("DOWNLOAD_SEM_DEFAULT")
    )
    try:
        sem = int(sem)
    except ValueError:
        sem = int(env.getattr("DOWNLOAD_SEM_DEFAULT"))
    return sem


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    if config is False:
        return env.getattr("PROGRESS_DEFAULT")
    val = (
        config.get("downloadbars")
        if config.get("downloadbars") is not None
        else config.get("advanced_options", {}).get("downloadbars")
    )
    return val if val is not None else env.getattr("PROGRESS_DEFAULT")


@wrapper.config_reader
def get_cache_mode(config=None):
    if cache_mode_helper(config=config) == "sqlite":
        return Disk
    else:
        return JSONDisk


def cache_mode_helper(config=None):
    if config is False:
        return env.getattr("CACHEDEFAULT")
    if config is None:
        config = config_file.open_config()
    data = (
        config.get("cache-mode")
        or config.get("advanced_options", {}).get("cache-mode")
        or env.getattr("CACHEDEFAULT")
    )
    if data == "disabled":
        return data
    if data in [env.getattr("CACHEDEFAULT"), "json"]:
        return data
    else:
        return env.getattr("CACHEDEFAULT")


@wrapper.config_reader
def get_rotate_logs(config=None):
    if config is False:
        return env.getattr("ROTATE_DEFAULT")
    value = (
        config.get("rotate_logs")
        if config.get("appendlog") is not None
        else config.get("advanced_options", {}).get("rotate_logs")
    )
    return value if value is not None else env.getattr("ROTATE_DEFAULT")


@wrapper.config_reader
def get_sanitizeDB(config=None):
    if config is False:
        return env.getattr("SANITIZE_DB_DEFAULT")
    val = (
        config.get("sanitize_text")
        if config.get("sanitize_text") is not None
        else config.get("advanced_options", {}).get("sanitize_text")
    )
    return val if val is not None else env.getattr("SANITIZE_DB_DEFAULT")


@wrapper.config_reader
def get_textType(config=None, mediatype=None):
    if config is False:
        return env.getattr("TEXT_TYPE_DEFAULT")
    value = (
        config.get("overwrites", {}).get(f"{mediatype}", {}).get("text_type_default")
        or config.get("text_type_default")
        or config.get("file_options", {}).get("text_type_default")
    )
    return (
        value
        if value in ["letter", "word"]
        else env.getattr("TEXT_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_TempDir(config=None, mediatype=None):
    if config is False:
        return env.getattr("TEMP_FOLDER_DEFAULT")
    return (
        config.get("overwrites", {}).get((mediatype or "").lower(), {}).get("temp_dir")
        or config.get("temp_dir")
        or config.get("advanced_options", {}).get("temp_dir")
        or env.getattr("TEMP_FOLDER_DEFAULT")
    )


@wrapper.config_reader
def get_truncation(config=None, mediatype=None):
    val = None
    if config is False:
        return env.getattr("TRUNCATION_DEFAULT")

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
    return val if val is not None else env.getattr("TRUNCATION_DEFAULT")


@wrapper.config_reader
def get_audios_overwrites(config=None):
    if config is False:
        return env.getattr("EMPTY_MEDIA_DEFAULT")
    return config.get("overwrites", {}).get("audios") or env.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_videos_overwrites(config=None):
    if config is False:
        return env.getattr("EMPTY_MEDIA_DEFAULT")
    return config.get("overwrites", {}).get("videos") or env.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_images_overwrites(config=None):
    if config is False:
        return env.getattr("EMPTY_MEDIA_DEFAULT")
    return config.get("overwrites", {}).get("images") or env.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_text_overwrites(config=None):
    if config is False:
        return env.getattr("EMPTY_MEDIA_DEFAULT")
    return config.get("overwrites", {}).get("text") or env.getattr(
        "EMPTY_MEDIA_DEFAULT"
    )


@wrapper.config_reader
def get_max_post_count(config=None):
    if config is False:
        return env.getattr("MAX_COUNT_DEFAULT")
    try:
        if config.get("max_post_count") is not None:
            return int(config.get("max_post_count"))
        elif config.get("download_options", {}).get("max_post_count") is not None:
            return int(config.get("download_options", {}).get("max_post_count"))
        return int(env.getattr("MAX_COUNT_DEFAULT"))
    except Exception:
        return env.getattr("MAX_COUNT_DEFAULT")


@wrapper.config_reader
def get_hash(config=None, mediatype=None):
    if config is False:
        return env.getattr("HASHED_DEFAULT")
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
    return env.getattr("HASHED_DEFAULT")


@wrapper.config_reader
def get_block_ads(config=None, mediatype=None):
    if config is False:
        return env.getattr("BLOCKED_ADS_DEFAULT")
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
    return env.getattr("BLOCKED_ADS_DEFAULT")
