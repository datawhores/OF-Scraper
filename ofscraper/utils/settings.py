import shutil

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants


def not_solo_thread():
    return (
        read_args.retriveArgs().downloadthreads != 0 and config_data.get_threads() != 0
    )


def get_key_mode():
    return read_args.retriveArgs().key_mode or config_data.get_key_mode()


def get_userlist(as_list=False):
    out = read_args.retriveArgs().user_list or config_data.get_default_userlist()
    if isinstance(out, str) and as_list == True:
        out = out.split(",")
        return set(map(lambda x: x.lower().strip(), out))
    elif as_list == True:
        out = set(map(lambda x: x.lower().strip(), out))
        return out
    elif isinstance(out, list) and as_list == False:
        out = set(map(lambda x: x.lower().strip(), out))
        return out.join(",")
    elif as_list == False:
        return out


def get_blacklist(as_list=False):
    out = read_args.retriveArgs().black_list or config_data.get_default_blacklist()
    if isinstance(out, str) and as_list == True:
        out = out.split(",")
        return set(map(lambda x: x.lower().strip(), out))
    elif as_list == True:
        out = set(map(lambda x: x.lower().strip(), out))
        return out
    elif isinstance(out, list) and as_list == False:
        out = set(map(lambda x: x.lower().strip(), out))
        return out.join(",")
    elif as_list == False:
        out = set(map(lambda x: x.lower().strip(), out))
        return out


def get_trunication(mediatype=None):
    return (
        read_args.retriveArgs().original
        or not config_data.get_truncation(mediatype=mediatype)
    ) == False


def get_cache_disabled():
    return (
        read_args.retriveArgs().no_cache or config_data.get_cache_mode() == "disabled"
    )


def get_dynamic_rules():
    return read_args.retriveArgs().dynamic_rules or config_data.get_dynamic()


def get_size_limit(mediatype=None):
    return read_args.retriveArgs().size_max or config_data.get_filesize_limit(
        mediatype=mediatype
    )


def get_size_min(mediatype=None):
    return read_args.retriveArgs().size_min or config_data.get_filesize_min(
        mediatype=mediatype
    )


def get_download_bars():
    return (
        read_args.retriveArgs().downloadbars or config_data.get_show_downloadprogress()
    )


def get_threads():
    return read_args.retriveArgs().downloadthreads or config_data.get_threads()


def get_max_post_count():
    return read_args.retriveArgs().max_count or config_data.get_max_post_count()


def get_mediatypes():
    return read_args.retriveArgs().mediatype or config_data.get_filter()


def get_download_bars():
    return (
        config_data.get_show_downloadprogress() or read_args.retriveArgs().downloadbars
    )


def get_auto_resume(mediatype=None):
    remove_file = (
        read_args.retriveArgs().no_auto_resume
        or not config_data.get_part_file_clean(mediatype=mediatype)
        or False
    )
    return remove_file == False


def get_discord():
    return read_args.retriveArgs().discord and read_args.retriveArgs().discord != "OFF"


def get_log():
    return constants.getattr("DEFAULT_LOG_LEVEL") or (
        read_args.retriveArgs().log and read_args.retriveArgs().log != "OFF"
    )


def get_log_level():
    if read_args.retriveArgs().log:
        return read_args.retriveArgs().log
    return constants.getattr("DEFAULT_LOG_LEVEL")


def get_mp4decrypt():
    return (
        config_data.get_mp4decrypt()
        or shutil.which(constants.getattr("MP4_DECRYPT"))
        or ""
    )


def get_ffmpeg():
    return (
        config_data.get_ffmpeg()
        or shutil.which(constants.getattr("FFMPEG_DECRYPT"))
        or ""
    )
