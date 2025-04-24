import shutil

import ofscraper.utils.ads as ads
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args

import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
from ofscraper.utils.args.accessors.areas import get_text_area

settings = {}


def get_args():
    return read_args.retriveArgs()


def update_args(args):
    write_args.setArgs(args)
    for key in settings.keys():
        settings[key] = setup_settings(key)


def get_settings(mediatype=None):
    global settings
    key = mediatype if mediatype is not None else "main"
    if not settings.get(key):
        settings[key] = setup_settings(mediatype)
    return settings[key]


def setup_settings(mediatype):
    merged = read_args.retriveArgs()
    merged.key_mode = read_args.retriveArgs().key_mode or config_data.get_key_mode()
    merged.cache_disabled = (
        read_args.retriveArgs().no_cache or config_data.get_cache_mode() == "disabled"
    )
    merged.api_cached_disabled = (
        read_args.retriveArgs().no_cache
        or read_args.retriveArgs().no_api_cache
        or config_data.get_cache_mode() == "api_disabled"
    )
    merged.dynamic_rules = (
        read_args.retriveArgs().dynamic_rules or config_data.get_dynamic()
    )
    merged.download_bars = (
        read_args.retriveArgs().downloadbars or config_data.get_show_downloadprogress()
    )
    merged.discord_level = (
        read_args.retriveArgs().discord_level or config_data.get_discord()
    )
    merged.log_level = read_args.retriveArgs().log_level or constants.getattr(
        "DEFAULT_LOG_LEVEL"
    )
    merged.keydb_api = read_args.retriveArgs().keydb_api or config_data.get_keydb_api()
    merged.trunicate = get_trunication(mediatype)
    merged.userlist = get_userlist()
    merged.blacklist = get_blacklist()
    merged.text_type = read_args.retriveArgs().text_type or config_data.get_textType(
        mediatype=mediatype
    )
    merged.space_replacer = (
        read_args.retriveArgs().space_replacer
        or config_data.get_spacereplacer(mediatype=mediatype)
    )
    merged.text_length = (
        read_args.retriveArgs().text_length
        or config_data.get_textlength(mediatype=mediatype)
    )
    merged.size_max = read_args.retriveArgs().size_max or config_data.get_filesize_max(
        mediatype=mediatype
    )
    merged.size_min = read_args.retriveArgs().size_min or config_data.get_filesize_min(
        mediatype=mediatype
    )
    merged.download_sems = (
        read_args.retriveArgs().downloadsem or config_data.get_download_semaphores()
    )
    merged.max_post_count = (
        read_args.retriveArgs().max_count or config_data.get_max_post_count()
    )
    merged.mediatypes = read_args.retriveArgs().mediatype or config_data.get_filter()
    merged.private_key = (
        read_args.retriveArgs().private_key or config_data.get_private_key()
    )
    merged.client_id = read_args.retriveArgs().client_id or config_data.get_client_id()
    merged.download_limit = get_download_limit()
    merged.length_max = get_max_length(mediatype)
    merged.length_min = get_min_length(mediatype)
    merged.neg_filter = get_neg_filter()
    merged.hash = config_data.get_hash(mediatype=mediatype)
    merged.post_script = (
        read_args.retriveArgs().post_script or config_data.get_post_script()
    )
    merged.download_script = (
        read_args.retriveArgs().download_script
        or config_data.get_post_download_script()
    )
    merged.auto_resume = get_auto_resume(mediatype)
    merged.cached_disabled = get_auto_after_enabled()
    merged.logs_expire_time=config_data.get_logs_expire()

    return merged


def get_download_text():
    return (
        get_text_area()
        or read_args.retriveArgs().text
        or read_args.retriveArgs().text_only
    )


def get_ffmpeg():
    return (
        config_data.get_ffmpeg()
        or shutil.which(constants.getattr("FFMPEG_DECRYPT"))
        or ""
    )


def get_auto_after_enabled():
    if read_args.retriveArgs().no_cache:
        return False
    if read_args.retriveArgs().no_api_cache:
        return False
    return config_data.get_enable_after()


def get_auto_resume(mediatype=None):
    if read_args.retriveArgs().no_auto_resume:
        return False
    return config_data.get_part_file_clean(mediatype=mediatype)


def get_neg_filter():
    neg = read_args.retriveArgs().neg_filter or []
    if read_args.retriveArgs().block_ads or config_data.get_block_ads():
        neg.append(ads.get_ad_key_words())
    return neg


def get_min_length(mediatype=None):
    if read_args.retriveArgs().length_min is not None:
        return read_args.retriveArgs().length_min
    return config_data.get_min_length(mediatype=mediatype)


def get_max_length(mediatype=None):
    if read_args.retriveArgs().length_max is not None:
        return read_args.retriveArgs().length_max
    return config_data.get_max_length(mediatype=mediatype)


def get_download_limit():
    out = read_args.retriveArgs().download_limit or config_data.get_download_limit()
    return max(out, 1024) if out else out


def get_trunication(mediatype=None):
    if read_args.retriveArgs().original:
        return False
    return config_data.get_truncation(mediatype=mediatype)


def get_userlist():
    out = read_args.retriveArgs().user_list or config_data.get_default_userlist()
    if isinstance(out, str):
        out = out.split(",")
    return out


def get_blacklist():
    out = read_args.retriveArgs().black_list or config_data.get_default_blacklist()
    if isinstance(out, str):
        out = out.split(",")
    return out
