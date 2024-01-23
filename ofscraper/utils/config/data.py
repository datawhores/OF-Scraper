r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

from diskcache import Disk, JSONDisk
from humanfriendly import parse_size

import ofscraper.utils.config.wrapper as wrapper
import ofscraper.utils.constants as constants


@wrapper.config_reader
def get_main_profile(config=None):
    if config == None:
        return constants.getattr("PROFILE_DEFAULT")
    return config.get(
        constants.getattr("mainProfile"), constants.getattr("PROFILE_DEFAULT")
    ) or constants.getattr("PROFILE_DEFAULT")


@wrapper.config_reader
def get_filesize_limit(config=None):
    if config == None:
        return constants.getattr("FILE_SIZE_LIMIT_DEFAULT")
    try:
        return parse_size(
            str(
                config.get("file_size_limit")
                or config.get("download_options", {}).get("file_size_limit")
                or constants.getattr("FILE_SIZE_LIMIT_DEFAULT")
            )
        )
    except:
        return 0


@wrapper.config_reader
def get_filesize_min(config=None):
    if config == None:
        return constants.getattr("FILE_SIZE_MIN_DEFAULT")
    try:
        return parse_size(
            str(
                config.get("file_size_min")
                or config.get("download_options", {}).get("file_size_min")
                or constants.getattr("FILE_SIZE_MIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_system_freesize(config=None):
    if config is None:
        return constants.getattr("SYSTEM_FREEMIN_DEFAULT")
    try:
        return parse_size(
            str(
                config.get("system_free_min")
                or config.get("download_options", {}).get("system_free_min")
                or constants.getattr("SYSTEM_FREEMIN_DEFAULT")
            )
        )
    except Exception:
        return 0


@wrapper.config_reader
def get_dirformat(config=None):
    if config == None:
        return constants.getattr("DIR_FORMAT_DEFAULT")
    return (
        config.get("dir_format")
        or config.get("file_options", {}).get("dir_format")
        or constants.getattr("DIR_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_fileformat(config=None):
    if config == None:
        return constants.getattr("FILE_FORMAT_DEFAULT")
    return (
        config.get("file_format")
        or config.get("file_options", {}).get("file_format")
        or constants.getattr("FILE_FORMAT_DEFAULT")
    )


@wrapper.config_reader
def get_textlength(config=None):
    if config == None:
        return constants.getattr("TEXTLENGTH_DEFAULT")
    try:
        return int(
            config.get("textlength") or config.get("file_options", {}).get("textlength")
        ) or constants.getattr("TEXTLENGTH_DEFAULT")
    except:
        return constants.getattr("TEXTLENGTH_DEFAULT")


@wrapper.config_reader
def get_date(config=None):
    if config == None:
        return constants.getattr("DATE_DEFAULT")
    return (
        config.get("date")
        or config.get("file_options", {}).get("date")
        or constants.getattr("DATE_DEFAULT")
    )


@wrapper.config_reader
def get_InfiniteLoop(config=None):
    if config == None:
        return constants.getattr("INFINITE_LOOP_DEFAULT")
    return (
        config.get("advanced_options", {}).get("infinite_loop")
        if config.get("advanced_options", {}).get("infinite_loop") != None
        else constants.getattr("INFINITE_LOOP_DEFAULT")
    )


@wrapper.config_reader
def get_allow_code_execution(config=None):
    if config == None:
        return constants.getattr("CODE_EXECUTION_DEFAULT")
    return (
        config.get("code-execution")
        or config.get("advanced_options", {}).get("code-execution")
        or constants.getattr("CODE_EXECUTION_DEFAULT")
    )


@wrapper.config_reader
def get_metadata(config=None):
    if config == None:
        return constants.getattr("METADATA_DEFAULT")
    return config.get("metadata", constants.getattr("METADATA_DEFAULT"))


@wrapper.config_reader
def get_threads(config=None):
    if config == None:
        return constants.getattr("THREADS_DEFAULT")
    threads = config.get("threads") or config.get("performance_options", {}).get(
        "threads"
    )
    threads = threads if threads is not None else constants.getattr("THREADS_DEFAULT")
    try:
        threads = int(threads)
    except ValueError:
        threads = int(constants.getattr("THREADS_DEFAULT"))
    return threads


@wrapper.config_reader
def get_mp4decrypt(config=None):
    if config == None:
        return constants.getattr("MP4DECRYPT_DEFAULT")
    return (
        config.get("mp4decrypt")
        or config.get("binary_options", {}).get("mp4decrypt")
        or constants.getattr("MP4DECRYPT_DEFAULT")
    )


@wrapper.config_reader
def get_ffmpeg(config=None):
    if config == None:
        return constants.getattr("FFMPEG_DEFAULT")
    return (
        config.get("ffmpeg")
        or config.get("binary_options", {}).get("ffmpeg")
        or constants.getattr("FFMPEG_DEFAULT")
    )


@wrapper.config_reader
def get_discord(config=None):
    if config == None:
        return constants.getattr("DISCORD_DEFAULT")
    return config.get("discord", constants.getattr("DISCORD_DEFAULT")) or ""


@wrapper.config_reader
def get_filter(config=None):
    if config == None:
        return constants.getattr("FILTER_DEFAULT")
    filter = (
        config.get("filter")
        or config.get("download_options", {}).get("filter")
        or constants.getattr("FILTER_DEFAULT")
    )
    if isinstance(filter, str):
        return list(map(lambda x: x.capitalize().strip(), filter.split(",")))
    elif isinstance(filter, list):
        return list(map(lambda x: x.capitalize(), filter))


@wrapper.config_reader
def responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")
    return (
        config.get("responsetype", {})
        or config.get("responsetype", {})
        or constants.getattr("RESPONSE_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_timeline_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    return (
        config.get("responsetype", {}).get("timeline")
        or config.get("responsetype", {}).get("post")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_post_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    return (
        config.get("responsetype", {}).get("post")
        or config.get("responsetype", {}).get("timeline")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["timeline"]
    )


@wrapper.config_reader
def get_archived_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    return (
        config.get("responsetype", {}).get("archived")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["archived"]
    )


@wrapper.config_reader
def get_stories_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    return (
        config.get("responsetype", {}).get("stories")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["stories"]
    )


@wrapper.config_reader
def get_highlights_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    return (
        config.get("responsetype", {}).get("highlights")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["highlights"]
    )


@wrapper.config_reader
def get_paid_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    return (
        config.get("responsetype", {}).get("paid")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["paid"]
    )


@wrapper.config_reader
def get_messages_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    return (
        config.get("responsetype", {}).get("message")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["message"]
    )


@wrapper.config_reader
def get_profile_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    return (
        config.get("responsetype", {}).get("profile")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["profile"]
    )


@wrapper.config_reader
def get_pinned_responsetype(config=None):
    if config == None:
        return constants.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    return (
        config.get("responsetype", {}).get("pinned")
        or constants.getattr("RESPONSE_TYPE_DEFAULT")["pinned"]
    )


@wrapper.config_reader
def get_spacereplacer(config=None):
    if config == None:
        return " "
    return (
        config.get("space-replacer")
        or config.get("file_options", {}).get("space-replacer")
        or constants.getattr("SPACE_REPLACER_DEFAULT")
    )


@wrapper.config_reader
def get_private_key(config=None):
    if config == None:
        return None
    return config.get("private-key") or config.get("cdm_options", {}).get("private-key")


@wrapper.config_reader
def get_client_id(config=None):
    if config == None:
        return None
    return config.get("client-id") or config.get("cdm_options", {}).get("client-id")


@wrapper.config_reader
def get_key_mode(config=None):
    if config == None:
        return constants.getattr("KEY_DEFAULT")
    value = config.get("key-mode-default") or config.get("cdm_options", {}).get(
        "key-mode-default"
    )

    return (
        value.lower()
        if value and value.lower() in set(constants.getattr("KEY_OPTIONS"))
        else constants.getattr("KEY_DEFAULT")
    )


@wrapper.config_reader
def get_keydb_api(config=None):
    if config == None:
        return ""
    return (
        config.get("keydb_api")
        or config.get("cdm_options", {}).get("keydb_api")
        or constants.getattr("KEYDB_DEFAULT")
    )


@wrapper.config_reader
def get_dynamic(config=None):
    if config == None:
        return constants.getattr("DYNAMIC_DEFAULT")
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
    if config == None:
        return False
    value = config.get(
        "partfileclean", config.get("download_options", {}).get("auto_resume")
    )
    return value if value is not None else True


@wrapper.config_reader
def get_backend(config=None):
    if config == None:
        return "aio"
    return (
        config.get("backend")
        or config.get("advanced_options", {}).get("backend")
        or constants.getattr("BACKEND_DEFAULT")
    )


@wrapper.config_reader
def get_download_semaphores(config=None):
    if config == None:
        return constants.getattr("DOWNLOAD_SEM_DEFAULT")
    sems = (
        config.get("download-sems")
        or config.get("performance_options", {}).get("download-sems")
        or constants.getattr("DOWNLOAD_SEM_DEFAULT")
    )
    try:
        sems = int(sems)
    except ValueError:
        sems = int(constants.getattr("DOWNLOAD_SEM_DEFAULT"))
    return sems


@wrapper.config_reader
def get_show_downloadprogress(config=None):
    if config == None:
        return constants.getattr("PROGRESS_DEFAULT")
    return (
        config.get("downloadbars")
        or config.get("advanced_options", {}).get("downloadbars")
        or constants.getattr("PROGRESS_DEFAULT")
    )


@wrapper.config_reader
def get_cache_mode(config=None):
    if cache_mode_helper(config=None) == "sqlite":
        return Disk
    else:
        return JSONDisk


@wrapper.config_reader
def cache_mode_helper(config=None):
    if config == None:
        return constants.getattr("CACHEDEFAULT")
    data = (
        config.get("cache-mode")
        or config.get("advanced_options", {}).get("cache-mode")
        or constants.getattr("CACHEDEFAULT")
    )
    if data == "disabled":
        return data
    if data in [constants.getattr("CACHEDEFAULT"), "json"]:
        return data
    else:
        return constants.getattr("CACHEDEFAULT")


@wrapper.config_reader
def get_appendlog(config=None):
    if config == None:
        return constants.getattr("APPEND_DEFAULT")
    value = config.get("appendlog") or config.get("advanced_options", {}).get(
        "appendlog"
    )
    return value if value is not None else constants.getattr("APPEND_DEFAULT")


@wrapper.config_reader
def get_sanitizeDB(config=None):
    if config is None:
        return constants.getattr("SANITIZE_DB_DEFAULT")
    return (
        config.get("sanitize_text")
        or config.get("advanced_options", {}).get("sanitize_text")
        or constants.getattr("SANITIZE_DB_DEFAULT")
    )


@wrapper.config_reader
def get_textType(config=None):
    if config is None:
        return constants.getattr("TEXT_TYPE_DEFAULT")
    value = config.get("text_type") or config.get("file_options", {}).get(
        "text_type_default"
    )
    return (
        value if value in ["letter", "word"] else constants.getattr("TEXT_TYPE_DEFAULT")
    )


@wrapper.config_reader
def get_TempDir(config=None):
    if config is None:
        return constants.getattr("TEMP_FOLDER_DEFAULT")
    return (
        config.get("temp_dir")
        or config.get("advanced_options", {}).get("temp_dir")
        or constants.getattr("TEMP_FOLDER_DEFAULT")
    )


@wrapper.config_reader
def get_truncation(config=None):
    if config is None:
        return constants.getattr("TRUNCATION_DEFAULT")
    val = config.get("file_options", {}).get("truncation_default") or config.get(
        "truncation_default"
    )
    if val is None:
        return constants.getattr("TRUNCATION_DEFAULT")
    return val
