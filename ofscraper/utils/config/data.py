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
import ofscraper.utils.config.wrapper as wrapper
import ofscraper.utils.constants as constants_attr


@wrapper.config_reader
def get_main_profile(config=None):
    if config == False:
        return constants.PROFILE_DEFAULT
    return config.get(
        constants_attr.getattr("mainProfile"), constants_attr.getattr("PROFILE_DEFAULT")
    ) or constants_attr.getattr("PROFILE_DEFAULT")


@wrapper.config_reader
def get_filesize_limit(config=None):
    if config == False:
        return constants.FILE_SIZE_LIMIT_DEFAULT
    try:
        if config.get("file_size_max") != None:
            size = config.get("file_size_max")
        elif config.get("download_options", {}).get("file_size_max"):
            size = config.get("download_options", {}).get("file_size_max")
        return parse_size(
            str(
                size
                if size != None
                else constants_attr.getattr("FILE_SIZE_MAX_DEFAULT")
            )
        )
    except:
        return 0


@wrapper.config_reader
def get_filesize_min(config=None):
    if config == False:
        return constants.FILE_SIZE_MIN_DEFAULT
    try:
        size = None
        if config.get("file_size_min") != None:
            size = config.get("file_size_min")
        elif config.get("download_options", {}).get("file_size_min"):
            size = config.get("download_options", {}).get("file_size_min")
        return parse_size(
            str(
                size
                if size != None
                else constants_attr.getattr("FILE_SIZE_MIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_system_freesize(config=None):
    if config == False:
        return constants.SYSTEM_FREEMIN_DEFAULT
    try:
        return parse_size(
            str(
                config.get("system_free_min")
                or config.get("download_options", {}).get("system_free_min")
                or constants_attr.getattr("SYSTEM_FREEMIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_dirformat(config=None):
    if config == False:
        return constants.DIR_FORMAT_DEFAULT
    return (
        config.get("dir_format")
        or config.get("file_options", {}).get("dir_format")
        or constants_attr.getattr("DIR_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_fileformat(config=None):
    if config == False:
        return constants.FILE_FORMAT_DEFAULT
    return (
        config.get("file_format")
        or config.get("file_options", {}).get("file_format")
        or constants_attr.getattr("FILE_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_textlength(config=None):
    if config == False:
        return constants.TEXTLENGTH_DEFAULT
    try:
        return int(
            config.get("textlength") or config.get("file_options", {}).get("textlength")
        ) or constants_attr.getattr("TEXTLENGTH_DEFAULT")
    except:
        return constants_attr.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None):
    if config == False:
        return constants.DATE_DEFAULT
    return (
        config.get("date")
        or config.get("file_options", {}).get("date")
        or constants_attr.getattr("DATE_DEFAULT")
    )


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    if config == False:
        return constants.INFINITE_LOOP_DEFAULT
    val = (
        config.get("infinite_loop_action_mode")
        if config.get("infinite_loop_action_mode") != None
        else config.get("advanced_options", {}).get("infinite_loop_action_mode")
    )
    return val if val != None else constants_attr.getattr("INFINITE_LOOP_DEFAULT")


@wrapper.config_reader
def get_disable_after(config=None):
    if config == False:
        return constants.DISABLE_AFTER_DEFAULT
    val = (
        config.get("disable_after_check")
        if config.get("infinite_loop_action_mode") != None
        else config.get("advanced_options", {}).get("disable_after_check")
    )
    return val if val != None else constants_attr.getattr("DISABLE_AFTER_DEFAULT")


@wrapper.config_reader
def get_default_userlist(config=None):
    if config == False:
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
def get_default_blacklist(config=None):
    if config == False:
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
    if config == False:
        return constants.CODE_EXECUTION_DEFAULT
    val = (
        config.get("code-execution")
        if config.get("code-execution") != None
        else config.get("advanced_options", {}).get("code-execution")
    )
    return val if val != None else constants_attr.getattr("CODE_EXECUTION_DEFAULT")


@wrapper.config_reader
def get_metadata(config=None):
    if config == False:
        return constants.METADATA_DEFAULT
    return config.get("metadata", constants_attr.getattr("METADATA_DEFAULT"))


@wrapper.config_reader
def get_threads(config=None):
    if config == False:
        return constants.THREADS_DEFAULT
    threads = config.get("threads") or config.get("performance_options", {}).get(
        "threads"
    )
    threads = (
        threads if threads is not None else constants_attr.getattr("THREADS_DEFAULT")
    )
    try:
        threads = int(threads)
    except ValueError:
        threads = int(constants_attr.getattr("THREADS_DEFAULT"))
    return threads


@wrapper.config_reader
def get_mp4decrypt(config=None):
    if config == False:
        return constants.MP4DECRYPT_DEFAULT
    return (
        config.get("mp4decrypt")
        or config.get("binary_options", {}).get("mp4decrypt")
        or constants_attr.getattr("MP4DECRYPT_DEFAULT")
    )


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config == False:
        return constants.FFMPEG_DEFAULT
    return (
        config.get("ffmpeg")
        or config.get("binary_options", {}).get("ffmpeg")
        or constants_attr.getattr("FFMPEG_DEFAULT")
    )


@wrapper.config_reader
def get_discord(config=None):
    if config == False:
        return constants.DISCORD_DEFAULT
    return config.get("discord", constants_attr.getattr("DISCORD_DEFAULT")) or ""


@wrapper.config_reader
def get_filter(config=None):
    if config == False:
        return constants.FILTER_DEFAULT
    filter = (
        config.get("filter")
        or config.get("download_options", {}).get("filter")
        or constants_attr.getattr("FILTER_DEFAULT")
    )
    if isinstance(filter, str):
        return list(map(lambda x: x.capitalize().strip(), filter.split(",")))
    elif isinstance(filter, list):
        return list(map(lambda x: x.capitalize(), filter))


@wrapper.config_reader
def responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT
    return (
        config.get("responsetype", {})
        or config.get("responsetype", {})
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_timeline_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["timeline"]
    return (
        config.get("timeline")
        or config.get("post")
        or config.get("responsetype", {}).get("timeline")
        or config.get("responsetype", {}).get("post")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_post_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["timeline"]
    return (
        config.get("post")
        or config.get("timeline")
        or config.get("responsetype", {}).get("post")
        or config.get("responsetype", {}).get("timeline")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_archived_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["archived"]
    return (
        config.get("archived")
        or config.get("responsetype", {}).get("archived")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    )


@wrapper.config_reader
def get_stories_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["stories"]
    return (
        config.get("stories")
        or config.get("responsetype", {}).get("stories")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    )


@wrapper.config_reader
def get_highlights_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["highlights"]
    return (
        config.get("highlights")
        or config.get("responsetype", {}).get("highlights")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    )


@wrapper.config_reader
def get_paid_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["paid"]
    return (
        config.get("paid")
        or config.get("responsetype", {}).get("paid")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    )


@wrapper.config_reader
def get_messages_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["message"]
    return (
        config.get("message")
        or config.get("responsetype", {}).get("message")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    )


@wrapper.config_reader
def get_profile_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["profile"]
    return (
        config.get("profile")
        or config.get("responsetype", {}).get("profile")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    )


@wrapper.config_reader
def get_pinned_responsetype(config=None):
    if config == False:
        return constants.RESPONSE_TYPE_DEFAULT["pinned"]
    return (
        config.get("pinned")
        or config.get("responsetype", {}).get("pinned")
        or constants_attr.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    )


@wrapper.config_reader
def get_spacereplacer(config=None):
    if config == False:
        return constants.SPACE_REPLACER_DEFAULT
    return (
        config.get("space-replacer")
        or config.get("file_options", {}).get("space-replacer")
        or constants_attr.getattr("SPACE_REPLACER_DEFAULT")
    )


@wrapper.config_reader
def get_private_key(config=None):
    if config == None or config == False:
        return None
    return config.get("private-key") or config.get("cdm_options", {}).get("private-key")


@wrapper.config_reader
def get_client_id(config=None):
    if config == None or config == False:
        return None
    return config.get("client-id") or config.get("cdm_options", {}).get("client-id")


@wrapper.config_reader
def get_key_mode(config=None):
    if config == False:
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
    if config == False:
        return constants.KEYDB_DEFAULT
    return (
        config.get("keydb_api")
        or config.get("cdm_options", {}).get("keydb_api")
        or constants_attr.getattr("KEYDB_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config == False:
        return constants.DYNAMIC_DEFAULT
    value = config.get("dynamic-mode-default") or config.get(
        "advanced_options", {}
    ).get("dynamic-mode-default")
    return (
        value.lower()
        if value
        and value.lower()
        in set(
            ["deviint", "digitalcriminals", "dv", "dev", "dc", "digital", "digitials"]
        )
        else "deviint"
    )


@wrapper.config_reader
def get_part_file_clean(config=None):
    if config == False:
        return constants.RESUME_DEFAULT
    if config.get("auto_resume"):
        return config.get("auto_resume")
    elif config.get("download_options", {}).get("auto_resume") != None:
        return config.get("download_options", {}).get("auto_resume")
    elif config.get("partfileclean") != None:
        return config.get("partfileclean") == False
    return constants_attr.getattr("RESUME_DEFAULT")


@wrapper.config_reader
def get_backend(config=None):
    if config == False:
        return constants.BACKEND_DEFAULT
    return (
        config.get("backend")
        or config.get("advanced_options", {}).get("backend")
        or constants_attr.getattr("BACKEND_DEFAULT")
    )


@wrapper.config_reader
def get_download_semaphores(config=None):
    if config == False:
        return constants.DOWNLOAD_SEM_DEFAULT
    sems = (
        config.get("download-sems")
        or config.get("performance_options", {}).get("download-sems")
        or constants_attr.getattr("DOWNLOAD_SEM_DEFAULT")
    )
    try:
        sems = int(sems)
    except ValueError:
        sems = int(constants_attr.getattr("DOWNLOAD_SEM_DEFAULT"))
    return sems


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    if config == False:
        return constants.PROGRESS_DEFAULT
    val = (
        config.get("downloadbars")
        if config.get("downloadbars") != None
        else config.get("advanced_options", {}).get("downloadbars")
    )
    return val if val != None else constants_attr.getattr("PROGRESS_DEFAULT")


@wrapper.config_reader
def get_cache_mode(config=None):
    if cache_mode_helper(config=config) == "sqlite":
        return Disk
    else:
        return JSONDisk


def cache_mode_helper(config=None):
    if config == False:
        return constants.CACHEDEFAULT
    if config == None:
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
    if config == False:
        return constants.APPEND_DEFAULT
    value = (
        config.get("appendlog")
        if config.get("appendlog") != None
        else config.get("advanced_options", {}).get("appendlog")
    )
    return value if value is not None else constants_attr.getattr("APPEND_DEFAULT")


@wrapper.config_reader
def get_sanitizeDB(config=None):
    if config == False:
        return constants.SANITIZE_DB_DEFAULT
    val = (
        config.get("sanitize_text")
        if config.get("sanitize_text") != None
        else config.get("advanced_options", {}).get("sanitize_text")
    )
    return val if val is not None else constants_attr.getattr("SANITIZE_DB_DEFAULT")


@wrapper.config_reader
def get_textType(config=None):
    if config == False:
        return constants.TEXT_TYPE_DEFAULT
    value = config.get("text_type_default") or config.get("file_options", {}).get(
        "text_type_default"
    )
    return (
        value
        if value in ["letter", "word"]
        else constants_attr.getattr("TEXT_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_TempDir(config=None):
    if config == False:
        return constants.TEMP_FOLDER_DEFAULT
    return (
        config.get("temp_dir")
        or config.get("advanced_options", {}).get("temp_dir")
        or constants_attr.getattr("TEMP_FOLDER_DEFAULT")
    )


@wrapper.config_reader
def get_truncation(config=None):
    if config == False:
        return constants.TRUNCATION_DEFAULT
    val = (
        config.get("file_options", {}).get("truncation_default")
        if config.get("file_options", {}).get("truncation_default") != None
        else config.get("truncation_default")
    )
    return val if val is not None else constants_attr.getattr("TRUNCATION_DEFAULT")


@wrapper.config_reader
def get_max_post_count(config=None):
    if config == False:
        return constants.MAX_COUNT_DEFAULT
    try:
        if config.get("max_post_count") != None:
            return int(config.get("max_post_count"))
        elif config.get("download_options", {}).get("max_post_count") != None:
            return config.get("download_options", {}).get("max_post_count")
        return int(constants_attr.getattr("MAX_COUNT_DEFAULT"))
    except:
        return constants_attr.getattr("MAX_COUNT_DEFAULT")
