from .values.main import load_main_config  # Contains all the prompt choice dictionaries

from .values.date import (
    load_date_config,
)  # Contains PROMPT_DATE_FORMAT, API_DATE_FORMAT
from .values.dynamic import load_dynamic_rules_config
from .values.general import (
    load_general_config,
)  # Contains SUPRESS_OUTPUTS, APP_TOKEN, disclaimers etc.
from .values.list import load_list_config
from .values.live import load_live_display_config
from .values.logger import load_log_config  # Assuming both functions are in logger.py
from .values.prompts import (
    load_prompts_config,
)  # Contains all the prompt choice dictionaries

# Placeholder imports for files where specific constants weren't previously specified,
# but which exist in your tree. You'll need to define these functions in their files.
from .values.rich import (
    load_rich_config,
)  # Assuming rich.py has a load_rich_config() function
from .values.system import (
    load_system_config,
)  # Assuming system.py has a load_system_config() function

from .values.time import load_expiry_config

# Nested 'action' directory
from .values.action.download import load_download_config  # From action/download.py
from .values.action.like import load_like_config  # From action/like.py
from .values.action.metadata import load_metadata_config  # From action/metadata.py

# Nested 'path' directory
from .values.path.bytes import load_path_bytes_config
from .values.path.files import load_file_paths_config
from .values.path.general import (
    load_general_paths_config,
)  # From path/general.py (BATCH_TEMPFILE_CLEANUP)
from .values.path.length import (
    load_max_lengths_config,
)  # From path/length.py (MAX_TEXT_LENGTH, WINDOWS_MAX_PATH_BYTES etc.)

# Nested 'req' directory
from .values.req.anon import load_req_config  # From req/anon.py (ANON_USERAGENT)
from .values.req.api import load_api_limits_config  # From req/api.py
from .values.req.cdm import load_cdm_config  # From req/cdm.py
from .values.req.discord import load_discord_config  # From req/discord.py
from .values.req.git import load_git_config  # From req/git.py
from .values.req.mpd import load_mpd_config  # From req/mpd.py
from .values.req.req import (
    load_network_config,
)  # From req/req.py (the "big one" with timeouts, semaphores etc.)
from .values.req.ratelimit import load_ratelimit_config


# Nested 'url' directory
from .values.url.other_url import load_other_urls_config  # From url/other_url.py
from .values.url.url import load_api_endpoints_config  # From url/url.py
from .values.url.dynamic import load_dynamic_url_config

# hardcoded values

# Module-level variables to store the cached configuration
_cached_settings = None


def get_all_configs():
    """
    Aggregates all application configuration settings by calling individual loader functions.
    This function ensures environment variables are read and defaults are applied.
    The configuration is loaded only once and then cached for subsequent calls.
    """
    global _cached_settings

    # If settings are already loaded, return the cached version
    if _cached_settings is not None:
        return _cached_settings

    # If you are using `python-dotenv` library to load from `.env` files,
    # you would typically call `load_dotenv()` here, once, at the very beginning
    # of your application's startup process (e.g., in your main script).
    # from dotenv import load_dotenv
    # load_dotenv()

    all_settings = {}

    # Update with settings from each logical group based on the imports in __init__.py
    all_settings.update(load_main_config())
    all_settings.update(load_date_config())
    all_settings.update(load_dynamic_rules_config())
    all_settings.update(load_general_config())
    all_settings.update(load_list_config())
    all_settings.update(load_live_display_config())
    all_settings.update(load_log_config())
    all_settings.update(load_prompts_config())
    all_settings.update(load_rich_config())
    all_settings.update(load_system_config())
    all_settings.update(load_expiry_config())

    # Nested 'action' directory
    all_settings.update(load_download_config())
    all_settings.update(load_like_config())
    all_settings.update(load_metadata_config())

    # Nested 'path' directory
    all_settings.update(load_path_bytes_config())
    all_settings.update(load_file_paths_config())
    all_settings.update(load_general_paths_config())
    all_settings.update(load_max_lengths_config())

    # Nested 'req' directory
    all_settings.update(load_req_config())
    all_settings.update(load_api_limits_config())
    all_settings.update(load_cdm_config())
    all_settings.update(load_discord_config())
    all_settings.update(load_git_config())
    all_settings.update(load_mpd_config())
    all_settings.update(load_network_config())
    all_settings.update(load_ratelimit_config())

    # Nested 'url' directory
    all_settings.update(load_other_urls_config())
    all_settings.update(load_api_endpoints_config())
    all_settings.update(load_dynamic_url_config())
    # Cache the loaded settings before returning
    _cached_settings = all_settings
    return _cached_settings
