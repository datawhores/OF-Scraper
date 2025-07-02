import threading
import re
from dotenv import load_dotenv
from copy import deepcopy
import ofscraper.utils.ads as ads
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
from ofscraper.utils.args.mutators.user import resetUserFilters as resetUserFiltersArgs,resetUserSelect as resetUserSelectArg
import ofscraper.utils.config.data as config_data
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.args.accessors.areas import get_text_area
from ofscraper.utils.of_env.load import load_env_files



# --- Globals for one-time initialization ---
_env_loaded = False
_init_lock = threading.Lock()


def _load_env_once():
    """
    Loads all environment-based configurations once.
    This function is thread-safe and ensures that config files are read
    and processed only one time during the application's lifecycle.
    """
    global _env_loaded
    # Quick check to avoid locking if already loaded
    if _env_loaded:
        return

    with _init_lock:
        # Double-check inside the lock to handle race conditions
        if _env_loaded:
            return
        # Load .env file if it exists
        load_dotenv(override=True)
        _env_loaded = True


# --- Main Settings Logic ---
settings = {}


def get_args(copy=False):
    if copy:
        args=read_args.retriveArgs()
        return deepcopy(args)
    else:
        return read_args.retriveArgs()


def update_args(args):
    global settings
    write_args.setArgs(args)
    settings = setup_settings()

def update_settings():
    global settings
    settings = setup_settings()



def get_settings():
    global settings
    _load_env_once()  # Ensures env is populated before settings are first calculated.
    if not settings:
        with _init_lock:
            # Check again inside lock for thread safety
            if not settings:
                settings = setup_settings()
    return settings


def setup_settings():
    merged=merged_settings()
    load_env_files(merged.env_files)
    return merged

def resetUserFilters():
    global settings
    args=resetUserFiltersArgs()
    write_args.setArgs(args)
    settings = setup_settings()

def resetUserSelect():
    global settings
    args=resetUserSelectArg()
    write_args.setArgs(args)
    settings = setup_settings()


def merged_settings():
    merged = deepcopy(read_args.retriveArgs())
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
    merged.log_level = read_args.retriveArgs().log_level or of_env.getattr(
        "DEFAULT_LOG_LEVEL"
    )
    merged.trunicate = get_trunication()
    merged.userlist = get_userlist()
    merged.blacklist = get_blacklist()
    merged.text_type = read_args.retriveArgs().text_type or config_data.get_textType()
    merged.space_replacer = (
        read_args.retriveArgs().space_replacer or config_data.get_spacereplacer()
    )
    merged.text_length = (
        read_args.retriveArgs().text_length or config_data.get_textlength()
    )
    merged.size_max = read_args.retriveArgs().size_max or config_data.get_filesize_max()
    merged.size_min = read_args.retriveArgs().size_min or config_data.get_filesize_min()
    merged.download_sems = (
        read_args.retriveArgs().downloadsem or config_data.get_download_semaphores()
    )
    merged.system_free_min=read_args.retriveArgs().system_free_min or config_data.get_system_freesize()
    merged.max_post_count = (
        read_args.retriveArgs().max_count or config_data.get_max_post_count()
    )
    merged.mediatypes = read_args.retriveArgs().mediatype or config_data.get_filter()
    merged.private_key = (
        read_args.retriveArgs().private_key or config_data.get_private_key()
    )
    merged.client_id = read_args.retriveArgs().client_id or config_data.get_client_id()
    merged.download_limit = get_download_limit()
    merged.length_max = get_max_length()
    merged.length_min = get_min_length()
    merged.neg_filter = get_neg_filter()
    merged.hash = config_data.get_hash()
    merged.post_script = (
        read_args.retriveArgs().post_script or config_data.get_post_script()
    )
    merged.after_action_script = (
        read_args.retriveArgs().after_action_script
        or config_data.get_after_action_script()
    )
    merged.naming_script = (
        read_args.retriveArgs().naming_script or config_data.get_naming_script()
    )
    merged.skip_download_script = (
        read_args.retriveArgs().skip_download_script
        or config_data.get_skip_download_script()
    )

    merged.after_download_script = (
        read_args.retriveArgs().after_download_script
        or config_data.get_after_download_script()
    )

    merged.auto_resume = get_auto_resume()
    merged.auto_after = get_auto_after_enabled()
    merged.cached_disabled = get_cached_disabled()
    merged.logs_expire_time = config_data.get_logs_expire()
    merged.ssl_verify = config_data.get_ssl_verify()
    merged.env_files=get_env_files()
    return merged


def get_download_text():
    return (
        get_text_area()
        or read_args.retriveArgs().text
        or read_args.retriveArgs().text_only
    )


def get_ffmpeg():
    return config_data.get_ffmpeg() or ""


def get_auto_after_enabled():
    if get_cached_disabled():
        return False
    return config_data.get_enable_after()


def get_cached_disabled():
    if read_args.retriveArgs().no_cache:
        return True
    if read_args.retriveArgs().no_api_cache:
        return True
    return False


def get_auto_resume():
    if read_args.retriveArgs().no_auto_resume:
        return False
    return config_data.get_part_file_clean()


def get_neg_filter():
    neg = read_args.retriveArgs().neg_filter or []
    if read_args.retriveArgs().block_ads or config_data.get_block_ads():
        neg.append(ads.get_ad_key_words())
    return neg


def get_min_length():
    if read_args.retriveArgs().length_min is not None:
        return read_args.retriveArgs().length_min
    return config_data.get_min_length()


def get_max_length():
    if read_args.retriveArgs().length_max is not None:
        return read_args.retriveArgs().length_max
    return config_data.get_max_length()


def get_download_limit():
    out = read_args.retriveArgs().download_limit or config_data.get_download_limit()
    return max(out, 1024) if out else out


def get_trunication():
    if read_args.retriveArgs().original:
        return False
    return config_data.get_truncation()


def get_userlist():
    out = read_args.retriveArgs().userlist or config_data.get_default_userlist()
    return _listhelper(out)


def get_blacklist():
    out = read_args.retriveArgs().blacklist or config_data.get_default_blacklist()
    return _listhelper(out)



def get_env_files():
    out = read_args.retriveArgs().env_files or config_data.get_env_files()
    if isinstance(out, str):
        out = re.split(r',| ', out)
    return out

def _listhelper(out):
    """
    Cleans and splits a string or cleans an existing list.
    - For strings, it splits by commas.
    - It trims whitespace from each item and removes any empty items.
    """
    if isinstance(out, list):
        # If it's already a list, just clean each item.
        return [str(item).strip() for item in out if str(item).strip()]
    elif isinstance(out, str):
        # If it's a string, split it by commas and then clean each item.
        split_list = out.split(',')
        return [item.strip() for item in split_list if item.strip()]
    # Return an empty list for any other input type (like None, int, etc.)
    return []