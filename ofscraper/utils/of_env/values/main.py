import os
import pathlib
import json  # Import json for parsing if you decide to allow dict/list overrides via env vars


def load_main_config():
    """
    Loads main configuration settings for various application behaviors,
    paths, and feature flags from environment variables.

    Returns:
        A dictionary containing all loaded default configuration settings.
    """
    config = {}

    # --- General Application Defaults ---
    # SANITIZE_DB_DEFAULT: Whether to sanitize the database by default.
    # Default: False
    config["SANITIZE_DB_DEFAULT"] = os.getenv(
        "OFSC_SANITIZE_DB_DEFAULT", "False"
    ).lower() in ("true", "1")

    # SUPPRESS_LOG_LEVEL: Log level to suppress output (integer representing level).
    # Default: 21 (likely a custom level between INFO and WARNING)
    config["SUPPRESS_LOG_LEVEL"] = int(os.getenv("OFSC_SUPPRESS_LOG_LEVEL", "21"))

    # RESUME_DEFAULT: Whether to resume downloads by default.
    # Default: True
    config["RESUME_DEFAULT"] = os.getenv("OFSC_RESUME_DEFAULT", "True").lower() in (
        "true",
        "1",
    )

    # CACHEDEFAULT: Default caching mechanism (e.g., "sqlite").
    # Default: "sqlite"
    config["CACHEDEFAULT"] = os.getenv("OFSC_CACHE_DEFAULT", "sqlite")

    # KEY_DEFAULT: Default key mode for content decryption.
    # Default: "cdrm"
    config["KEY_DEFAULT"] = os.getenv("OFSC_KEY_DEFAULT", "cdrm")

    # FILE_SIZE_MAX_DEFAULT: Default maximum file size allowed (bytes, 0 for no limit).
    # Default: 0
    config["FILE_SIZE_MAX_DEFAULT"] = int(os.getenv("OFSC_FILE_SIZE_MAX_DEFAULT", "0"))

    # FILE_SIZE_MIN_DEFAULT: Default minimum file size allowed (bytes, 0 for no limit).
    # Default: 0
    config["FILE_SIZE_MIN_DEFAULT"] = int(os.getenv("OFSC_FILE_SIZE_MIN_DEFAULT", "0"))

    # MIN_LENGTH_DEFAULT: Default minimum content length (e.g., for video duration).
    # Default: 0
    config["MIN_LENGTH_DEFAULT"] = int(os.getenv("OFSC_MIN_LENGTH_DEFAULT", "0"))

    # MAX_LENGTH_DEFAULT: Default maximum content length.
    # Default: 0
    config["MAX_LENGTH_DEFAULT"] = int(os.getenv("OFSC_MAX_LENGTH_DEFAULT", "0"))

    # TEXTLENGTH_DEFAULT: Default text length setting.
    # Default: 0
    config["TEXTLENGTH_DEFAULT"] = int(os.getenv("OFSC_TEXTLENGTH_DEFAULT", "0"))

    # SPACE_REPLACER_DEFAULT: Character to replace spaces in paths/names.
    # Default: " " (space)
    config["SPACE_REPLACER_DEFAULT"] = os.getenv("OFSC_SPACE_REPLACER_DEFAULT", " ")

    # PROGRESS_DEFAULT: Whether to show progress bars by default.
    # Default: False
    config["PROGRESS_DEFAULT"] = os.getenv(
        "OFSC_PROGRESS_DEFAULT", "False"
    ).lower() in ("true", "1")

    # SAVE_PATH_DEFAULT: Default base path for saving downloaded content.
    # Default: pathlib.Path.home() / "Data/ofscraper"
    config["SAVE_PATH_DEFAULT"] = os.getenv(
        "OFSC_SAVE_PATH_DEFAULT", str(pathlib.Path.home() / "Data/ofscraper")
    )

    # DATE_DEFAULT: Default date format string.
    # Default: "MM-DD-YYYY"
    config["DATE_DEFAULT"] = os.getenv("OFSC_DATE_DEFAULT", "MM-DD-YYYY")

    # PROFILE_DEFAULT: Default profile name.
    # Default: "main_profile"
    config["PROFILE_DEFAULT"] = os.getenv("OFSC_PROFILE_DEFAULT", "main_profile")

    # PREMIUM_DEFAULT: Default category for premium content.
    # Default: "Premium"
    config["PREMIUM_DEFAULT"] = os.getenv("OFSC_PREMIUM_DEFAULT", "Premium")

    # FFMPEG_DEFAULT: Default path for FFmpeg executable.
    # Default: "" (empty string)
    config["FFMPEG_DEFAULT"] = os.getenv("OFSC_FFMPEG_DEFAULT", "")

    # DISCORD_DEFAULT: Default Discord webhook URL or related setting.
    # Default: "" (empty string)
    config["DISCORD_DEFAULT"] = os.getenv("OFSC_DISCORD_DEFAULT", "")

    # THREADS_DEFAULT: Default number of threads for operations.
    # Default: 2
    config["THREADS_DEFAULT"] = int(os.getenv("OFSC_THREADS_DEFAULT", "2"))

    # DOWNLOAD_SEM_DEFAULT: Default semaphore limit for downloads.
    # Default: 6
    config["DOWNLOAD_SEM_DEFAULT"] = int(os.getenv("OFSC_DOWNLOAD_SEM_DEFAULT", "6"))

    # TEXT_TYPE_DEFAULT: Default text type processing.
    # Default: "letter"
    config["TEXT_TYPE_DEFAULT"] = os.getenv("OFSC_TEXT_TYPE_DEFAULT", "letter")

    # TRUNCATION_DEFAULT: Whether truncation is enabled by default.
    # Default: True
    config["TRUNCATION_DEFAULT"] = os.getenv(
        "OFSC_TRUNCATION_DEFAULT", "True"
    ).lower() in ("true", "1")

    # MAX_COUNT_DEFAULT: Default maximum count for certain operations.
    # Default: 0 (no limit)
    config["MAX_COUNT_DEFAULT"] = int(os.getenv("OFSC_MAX_COUNT_DEFAULT", "0"))

    # TEMP_FOLDER_DEFAULT: Default temporary folder path. Defaults to None.
    config["TEMP_FOLDER_DEFAULT"] = os.getenv("OFSC_TEMP_FOLDER_DEFAULT", None)

    # ROTATE_DEFAULT: Whether to rotate content by default.
    # Default: True
    config["ROTATE_DEFAULT"] = os.getenv("OFSC_ROTATE_DEFAULT", "True").lower() in (
        "true",
        "1",
    )

    # SYSTEM_FREEMIN_DEFAULT: Minimum free system space required (bytes/MB?).
    # Default: 0
    config["SYSTEM_FREEMIN_DEFAULT"] = int(
        os.getenv("OFSC_SYSTEM_FREEMIN_DEFAULT", "0")
    )

    # AVATAR_DEFAULT: Whether avatars are included by default.
    # Default: True
    config["AVATAR_DEFAULT"] = os.getenv("OFSC_AVATAR_DEFAULT", "True").lower() in (
        "true",
        "1",
    )

    # INFINITE_LOOP_DEFAULT: Whether infinite loop mode is enabled by default.
    # Default: False
    config["INFINITE_LOOP_DEFAULT"] = os.getenv(
        "OFSC_INFINITE_LOOP_DEFAULT", "False"
    ).lower() in ("true", "1")

    # ENABLE_AUTO_AFTER_DEFAULT: Whether auto-after processing is enabled by default.
    # Default: False
    config["ENABLE_AUTO_AFTER_DEFAULT"] = os.getenv(
        "OFSC_ENABLE_AUTO_AFTER_DEFAULT", "False"
    ).lower() in ("true", "1")

    # DEFAULT_USER_LIST: Default user list to use.
    # Default: "main"
    config["DEFAULT_USER_LIST"] = os.getenv("OFSC_DEFAULT_USER_LIST", "main")

    # DEFAULT_BLACK_LIST: Default blacklist name.
    # Default: "" (empty string)
    config["DEFAULT_BLACK_LIST"] = os.getenv("OFSC_DEFAULT_BLACK_LIST", "")

    # HASHED_DEFAULT: Default hashing setting. Defaults to None.
    config["HASHED_DEFAULT"] = os.getenv("OFSC_HASHED_DEFAULT", None)

    # BLOCKED_ADS_DEFAULT: Whether ads are blocked by default.
    # Default: False
    config["BLOCKED_ADS_DEFAULT"] = os.getenv(
        "OFSC_BLOCKED_ADS_DEFAULT", "False"
    ).lower() in ("true", "1")

    # DEFAULT_LOG_LEVEL: Default logging level.
    # Default: "DEBUG"
    config["DEFAULT_LOG_LEVEL"] = os.getenv("OFSC_DEFAULT_LOG_LEVEL", "DEBUG")

    # INCLUDE_LABELS_ALL: Whether to include all labels by default.
    # Default: False
    config["INCLUDE_LABELS_ALL"] = os.getenv(
        "OFSC_INCLUDE_LABELS_ALL", "False"
    ).lower() in ("true", "1")

    # DISCORD_THREAD_OVERRIDE: Whether to override Discord threading.
    # Default: False
    config["DISCORD_THREAD_OVERRIDE"] = os.getenv(
        "OFSC_DISCORD_THREAD_OVERRIDE", "False"
    ).lower() in ("true", "1")

    # DISCORD_ASYNC: Whether Discord integration is asynchronous.
    # Default: False
    config["DISCORD_ASYNC"] = os.getenv("OFSC_DISCORD_ASYNC", "False").lower() in (
        "true",
        "1",
    )

    # USE_WIV_CACHE_KEY: Whether to use Widevine cache key.
    # Default: True
    config["USE_WIV_CACHE_KEY"] = os.getenv(
        "OFSC_USE_WIV_CACHE_KEY", "True"
    ).lower() in ("true", "1")

    # AFTER_ACTION_SCRIPT_DEFAULT: Default path for a script to run after download. Defaults to None.
    config["AFTER_ACTION_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_AFTER_ACTION_SCRIPT_DEFAULT", None
    )

    # POST_SCRIPT_DEFAULT: Default path for a general post-processing script. Defaults to None.
    config["POST_SCRIPT_DEFAULT"] = os.getenv("OFSC_POST_SCRIPT_DEFAULT", None)

    # SKIP_DOWNLOAD_SCRIPT_DEFAULT: Default path for a general download-skipping script. Defaults to None.
    config["SKIP_DOWNLOAD_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_SKIP_DOWNLOAD_SCRIPT_DEFAULT", None
    )

    # AFTER_DOWNLOAD_SCRIPT_DEFAULT: Default path for a script that runs after download. Defaults to None.
    config["AFTER_DOWNLOAD_SCRIPT_DEFAULT"] = os.getenv("OFSC_AFTER_DOWNLOAD_SCRIPT_DEFAULT", None)

   
    # ENV_FILES_DEFAULT: Default path for a file(s) used to import env variables. Defaults to None.
    config["ENV_FILES_DEFAULT"] = os.getenv("OFSC_ENV_FILES_DEFAULT", "")
   
    # SKIP_DOWNLOAD_SCRIPT_DEFAULT: Default path for a general download-skipping script. Defaults to None.
    config["SKIP_DOWNLOAD_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_SKIP_DOWNLOAD_SCRIPT_DEFAULT", None
    )

    # NAMING_SCRIPT_DEFAULT: Default path for a general naming-processing script. Defaults to None.
    config["NAMING_SCRIPT_DEFAULT"] = os.getenv("OFSC_NAMING_SCRIPT_DEFAULT", None)

    # DOWNLOAD_LIMIT_DEFAULT: Default limit for downloads (integer, 0 for no limit).
    # Default: 0
    config["DOWNLOAD_LIMIT_DEFAULT"] = int(
        os.getenv("OFSC_DOWNLOAD_LIMIT_DEFAULT", "0")
    )

    # --- Format String Defaults (These are often user-configurable, but have internal defaults) ---
    # DIR_FORMAT_DEFAULT: Default directory naming format string.
    # Default: "{model_username}/{responsetype}/{mediatype}/"
    config["DIR_FORMAT_DEFAULT"] = os.getenv(
        "OFSC_DIR_FORMAT_DEFAULT", "{model_username}/{responsetype}/{mediatype}/"
    )

    # FILE_FORMAT_DEFAULT: Default file naming format string.
    # Default: "{filename}.{ext}"
    config["FILE_FORMAT_DEFAULT"] = os.getenv(
        "OFSC_FILE_FORMAT_DEFAULT", "{filename}.{ext}"
    )

    # METADATA_DEFAULT: Default metadata file path format.
    # Default: "{configpath}/{profile}/.data/{model_id}"
    config["METADATA_DEFAULT"] = os.getenv(
        "OFSC_METADATA_DEFAULT", "{configpath}/{profile}/.data/{model_id}"
    )

    # --- Complex Defaults (Better as Python Constants, not environment variables) ---
    # RESPONSE_TYPE_DEFAULT: Mapping of response types to display names.
    # Default: A dictionary.
    # If you absolutely need to override this via environment, it would require
    # providing a JSON string via the environment variable and parsing it.
    # For now, defining it directly as a Python constant is robust.
    response_type_default_env = os.getenv("OFSC_RESPONSE_TYPE_DEFAULT")
    if response_type_default_env:
        try:
            config["RESPONSE_TYPE_DEFAULT"] = json.loads(response_type_default_env)
        except json.JSONDecodeError:
            print(
                f"Warning: OFSC_RESPONSE_TYPE_DEFAULT environment variable '{response_type_default_env}' is not valid JSON. Using default dictionary."
            )
            config["RESPONSE_TYPE_DEFAULT"] = {
                "message": "Messages",
                "timeline": "Posts",
                "archived": "Archived",
                "paid": "Messages",
                "stories": "Stories",
                "highlights": "Stories",
                "profile": "Profile",
                "pinned": "Posts",
                "streams": "Streams",
            }
    else:
        config["RESPONSE_TYPE_DEFAULT"] = {
            "message": "Messages",
            "timeline": "Posts",
            "archived": "Archived",
            "paid": "Messages",
            "stories": "Stories",
            "highlights": "Stories",
            "profile": "Profile",
            "pinned": "Posts",
            "streams": "Streams",
        }

    # EMPTY_MEDIA_DEFAULT: Default empty media dictionary.
    # Default: {} (empty dictionary)
    empty_media_default_env = os.getenv("OFSC_EMPTY_MEDIA_DEFAULT")
    if empty_media_default_env:
        try:
            config["EMPTY_MEDIA_DEFAULT"] = json.loads(empty_media_default_env)
        except json.JSONDecodeError:
            print(
                f"Warning: OFSC_EMPTY_MEDIA_DEFAULT environment variable '{empty_media_default_env}' is not valid JSON. Using default empty dictionary."
            )
            config["EMPTY_MEDIA_DEFAULT"] = {}
    else:
        config["EMPTY_MEDIA_DEFAULT"] = {}

    # FILTER_DEFAULT: Default filter list.
    # Default: ["Images", "Audios", "Videos"] (list of strings)
    # If provided via environment, expect comma-separated string, e.g., "Images,Videos"
    filter_default_env = os.getenv("OFSC_FILTER_DEFAULT")
    if filter_default_env:
        config["FILTER_DEFAULT"] = [f.strip() for f in filter_default_env.split(",")]
    else:
        config["FILTER_DEFAULT"] = ["Images", "Audios", "Videos"]

    ssl_verify = os.getenv("OFSC_SSL_VALIDATION_DEFAULT", True)
    config["SSL_VALIDATION_DEFAULT"] = ssl_verify

    return config
