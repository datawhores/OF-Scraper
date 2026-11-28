import json  # Import json for parsing if you decide to allow dict/list overrides via env vars
import os
import pathlib

import ofscraper.utils.const as const


def load_main_config():
    """
    Loads main configuration settings for various application behaviors,
    paths, and feature flags from environment variables.

    Returns:
        A dictionary containing all loaded default configuration settings.
    """
    config = {}

    # --- General Application Defaults ---
    # SANITIZE_DB_DEFAULT: Default for `advanced_options.sanitize_text` (whether post and message text is sanitised before storing in the database).
    # Default: False
    config["SANITIZE_DB_DEFAULT"] = os.getenv(
        "OFSC_SANITIZE_DB_DEFAULT", "False"
    ).lower() in ("true", "1")

    # SUPPRESS_LOG_LEVEL: Defined but not read anywhere.
    # Default: 21 (likely a custom level between INFO and WARNING)
    config["SUPPRESS_LOG_LEVEL"] = int(os.getenv("OFSC_SUPPRESS_LOG_LEVEL", "21"))

    # RESUME_DEFAULT: Default for `download_options.auto_resume` (whether leftover `.part` files are resumed).
    # Default: True
    config["RESUME_DEFAULT"] = os.getenv("OFSC_RESUME_DEFAULT", "True").lower() in (
        "true",
        "1",
    )

    # CACHEDEFAULT: Default for `advanced_options.cache-mode` (`sqlite`, `json`, `disabled` or `api_disabled`).
    # Default: "sqlite"
    config["CACHEDEFAULT"] = os.getenv("OFSC_CACHE_DEFAULT", "sqlite")

    # KEY_DEFAULT: Default for `cdm_options.key-mode-default` (`manual`; `cdrm` is deprecated because its service no longer works).
    # Default: "manual" (cdrm is deprecated: its service no longer works)
    config["KEY_DEFAULT"] = os.getenv("OFSC_KEY_DEFAULT", "manual")
    config["KEY_OPTIONS"] = const.KEY_OPTIONS

    # FILE_SIZE_MAX_DEFAULT: Default for `content_filter_options.file_size_max` (maximum file size in bytes; 0 means no limit).
    # Default: 0
    config["FILE_SIZE_MAX_DEFAULT"] = int(os.getenv("OFSC_FILE_SIZE_MAX_DEFAULT", "0"))

    # FILE_SIZE_MIN_DEFAULT: Default for `content_filter_options.file_size_min` (minimum file size in bytes; 0 means no limit).
    # Default: 0
    config["FILE_SIZE_MIN_DEFAULT"] = int(os.getenv("OFSC_FILE_SIZE_MIN_DEFAULT", "0"))

    # MIN_LENGTH_DEFAULT: Default for `content_filter_options.length_min` (minimum video duration in seconds; 0 means no limit).
    # Default: 0
    config["MIN_LENGTH_DEFAULT"] = int(os.getenv("OFSC_MIN_LENGTH_DEFAULT", "0"))

    # MAX_LENGTH_DEFAULT: Default for `content_filter_options.length_max` (maximum video duration in seconds; 0 means no limit).
    # Default: 0
    config["MAX_LENGTH_DEFAULT"] = int(os.getenv("OFSC_MAX_LENGTH_DEFAULT", "0"))

    # TEXTLENGTH_DEFAULT: Default for `file_options.textlength` (maximum post text length in filenames, in letters or words per `TEXT_TYPE_DEFAULT`; 0 means no limit).
    # Default: 0
    config["TEXTLENGTH_DEFAULT"] = int(os.getenv("OFSC_TEXTLENGTH_DEFAULT", "0"))

    # SPACE_REPLACER_DEFAULT: Default for `file_options.space_replacer` (character replacing spaces in filename text).
    # Default: " " (space)
    config["SPACE_REPLACER_DEFAULT"] = os.getenv("OFSC_SPACE_REPLACER_DEFAULT", " ")

    # PROGRESS_DEFAULT: Default for `advanced_options.downloadbars` (whether to show per-file download progress bars).
    # Default: False
    config["PROGRESS_DEFAULT"] = os.getenv(
        "OFSC_PROGRESS_DEFAULT", "False"
    ).lower() in ("true", "1")

    # SAVE_PATH_DEFAULT: Default for `file_options.save_location` (root folder for downloads).
    # Default: pathlib.Path.home() / "Data/ofscraper"
    config["SAVE_PATH_DEFAULT"] = os.getenv(
        "OFSC_SAVE_PATH_DEFAULT", str(pathlib.Path.home() / "Data/ofscraper")
    )

    # DATE_DEFAULT: Default for `file_options.date` (arrow date format for the `{date}` placeholder).
    # Default: "MM-DD-YYYY"
    config["DATE_DEFAULT"] = os.getenv("OFSC_DATE_DEFAULT", "MM-DD-YYYY")

    # PROFILE_DEFAULT: Default for `main_profile` (profile folder name in the config directory).
    # Default: "main_profile"
    config["PROFILE_DEFAULT"] = os.getenv("OFSC_PROFILE_DEFAULT", "main_profile")

    # PREMIUM_DEFAULT: Defined but not read anywhere.
    # Default: "Premium"
    config["PREMIUM_DEFAULT"] = os.getenv("OFSC_PREMIUM_DEFAULT", "Premium")

    # FFMPEG_DEFAULT: Default for `binary_options.ffmpeg` (path to the ffmpeg executable).
    # Default: "" (empty string)
    config["FFMPEG_DEFAULT"] = os.getenv("OFSC_FFMPEG_DEFAULT", "")

    # DISCORD_DEFAULT: Default for `discord` (Discord webhook URL for log messages).
    # Default: "" (empty string)
    config["DISCORD_DEFAULT"] = os.getenv("OFSC_DISCORD_DEFAULT", "")

    # THREADS_DEFAULT: Defined but not read anywhere.
    # Default: 2
    config["THREADS_DEFAULT"] = int(os.getenv("OFSC_THREADS_DEFAULT", "2"))

    # DOWNLOAD_SEM_DEFAULT: Default for `performance_options.download_sems` (number of concurrent downloads).
    # Default: 6
    config["DOWNLOAD_SEM_DEFAULT"] = int(os.getenv("OFSC_DOWNLOAD_SEM_DEFAULT", "6"))

    # FANSLY_STREAM_SEGMENTS: How many files of one Fansly stream (HLS or DASH) are fetched at once.
    # 0 leaves the whole stream to ffmpeg, one segment after another, with no resume.
    # Default: 8
    config["FANSLY_STREAM_SEGMENTS"] = int(os.getenv("OFSC_FANSLY_STREAM_SEGMENTS", "8"))

    # SILENT_RECHECKS: How many times a Fansly video saved without sound, because the CDN
    # refused its audio, is checked again on later runs before it is kept as it is.
    # Default: 3
    config["SILENT_RECHECKS"] = int(os.getenv("OFSC_SILENT_RECHECKS", "3"))

    # FANSLY_FULL_SCAN_DAYS: A Fansly repeat run scans an area fully when its last full
    # scan is older than this many days; otherwise it may stop where the last scan began.
    # 0 scans fully every time.
    # Default: 7
    config["FANSLY_FULL_SCAN_DAYS"] = int(os.getenv("OFSC_FANSLY_FULL_SCAN_DAYS", "7"))

    # TEXT_TYPE_DEFAULT: Default for `file_options.text_type_default` (`letter` or `word`).
    # Default: "letter"
    config["TEXT_TYPE_DEFAULT"] = os.getenv("OFSC_TEXT_TYPE_DEFAULT", "letter")

    # TRUNCATION_DEFAULT: Default for `file_options.truncation_default` (whether long file paths are shortened to fit OS limits).
    # Default: True
    config["TRUNCATION_DEFAULT"] = os.getenv(
        "OFSC_TRUNCATION_DEFAULT", "True"
    ).lower() in ("true", "1")

    # FILENAME_COLLISION_DEFAULT: What to do when a download's path is already
    # taken by a different media. "media_id" appends _<media_id>; "overwrite"
    # keeps the old behaviour (one file replaces the other).
    # Default: media_id
    config["FILENAME_COLLISION_DEFAULT"] = os.getenv(
        "OFSC_FILENAME_COLLISION_DEFAULT", "media_id"
    )

    # MAX_COUNT_DEFAULT: Default for `download_options.max_post_count` (maximum media items to process per creator; 0 means no limit).
    # Default: 0 (no limit)
    config["MAX_COUNT_DEFAULT"] = int(os.getenv("OFSC_MAX_COUNT_DEFAULT", "0"))

    # TEMP_FOLDER_DEFAULT: Default for `advanced_options.temp_dir` (root folder for `.part` files).
    config["TEMP_FOLDER_DEFAULT"] = os.getenv("OFSC_TEMP_FOLDER_DEFAULT", None)

    # ROTATE_DEFAULT: Default for `advanced_options.rotate_logs` (whether each run writes its own log file in a per-day folder).
    # Default: True
    config["ROTATE_DEFAULT"] = os.getenv("OFSC_ROTATE_DEFAULT", "True").lower() in (
        "true",
        "1",
    )

    # SYSTEM_FREEMIN_DEFAULT: Default for `download_options.system_free_min` (minimum free disk space in bytes; 0 disables the check).
    # Default: 0
    config["SYSTEM_FREEMIN_DEFAULT"] = int(
        os.getenv("OFSC_SYSTEM_FREEMIN_DEFAULT", "0")
    )

    # AVATAR_DEFAULT: Defined but not read anywhere.
    # Default: True
    config["AVATAR_DEFAULT"] = os.getenv("OFSC_AVATAR_DEFAULT", "True").lower() in (
        "true",
        "1",
    )

    # INFINITE_LOOP_DEFAULT: Default for `advanced_options.infinite_loop_action_mode` (whether action mode prompts to continue after each run).
    # Default: False
    config["INFINITE_LOOP_DEFAULT"] = os.getenv(
        "OFSC_INFINITE_LOOP_DEFAULT", "False"
    ).lower() in ("true", "1")

    # INCREMENTAL_DOWNLOADS_DEFAULT: Default for `advanced_options.incremental_downloads` (also reads `OFSC_ENABLE_AUTO_AFTER_DEFAULT`).
    # Default:
    incremental_envs = [
        os.getenv("OFSC_INCREMENTAL_DOWNLOADS_DEFAULT"),
        os.getenv("OFSC_ENABLE_AUTO_AFTER_DEFAULT"),
    ]

    # Find the first environment variable that is actually set (not None)
    active_env_val = next((val for val in incremental_envs if val is not None), None)
    if active_env_val is not None:
        config["INCREMENTAL_DOWNLOADS_DEFAULT"] = active_env_val.lower() in (
            "true",
            "1",
        )
    else:
        config["INCREMENTAL_DOWNLOADS_DEFAULT"] = True

    # DEFAULT_USER_LIST: Default for `advanced_options.default_user_list` (user lists selected when `--user-list` isn't given).
    # Default: "main"
    config["DEFAULT_USER_LIST"] = os.getenv("OFSC_DEFAULT_USER_LIST", "main")

    # DEFAULT_BLACK_LIST: Default for `advanced_options.default_black_list` (user lists excluded when `--black-list` isn't given).
    # Default: "" (empty string)
    config["DEFAULT_BLACK_LIST"] = os.getenv("OFSC_DEFAULT_BLACK_LIST", "")

    # HASHED_DEFAULT: Default for `advanced_options.remove_hash_match` (`true`, `false` or `None`).
    config["HASHED_DEFAULT"] = os.getenv("OFSC_HASHED_DEFAULT", None)

    # BLOCKED_ADS_DEFAULT: Default for `content_filter_options.block_ads` (whether posts matching the ad regex are skipped).
    # Default: False
    config["BLOCKED_ADS_DEFAULT"] = os.getenv(
        "OFSC_BLOCKED_ADS_DEFAULT", "False"
    ).lower() in ("true", "1")

    # DEFAULT_LOG_LEVEL: Default log file level when `--log` isn't given.
    # Default: "DEBUG"
    config["DEFAULT_LOG_LEVEL"] = os.getenv("OFSC_DEFAULT_LOG_LEVEL", "DEBUG")

    # INCLUDE_LABELS_ALL: When on, `--posts all` (and `--download-area all` / `--like-area all`) also includes the Labels area.
    # Default: False
    config["INCLUDE_LABELS_ALL"] = os.getenv(
        "OFSC_INCLUDE_LABELS_ALL", "False"
    ).lower() in ("true", "1")

    # LABELS_CONCURRENCY: How many labels are paged at the same time.
    # Default: 2
    config["LABELS_CONCURRENCY"] = int(os.getenv("OFSC_LABELS_CONCURRENCY", "2"))

    # DISCORD_THREAD_OVERRIDE: Defined but not read anywhere.
    # Default: False
    config["DISCORD_THREAD_OVERRIDE"] = os.getenv(
        "OFSC_DISCORD_THREAD_OVERRIDE", "False"
    ).lower() in ("true", "1")

    # DISCORD_ASYNC: When on, sends Discord webhook log messages asynchronously instead of synchronously.
    # Default: False
    config["DISCORD_ASYNC"] = os.getenv("OFSC_DISCORD_ASYNC", "False").lower() in (
        "true",
        "1",
    )

    # USE_WIV_CACHE_KEY: Whether to cache Widevine decryption keys by PSSH (`keyhelpers.py`).
    # Default: True
    config["USE_WIV_CACHE_KEY"] = os.getenv(
        "OFSC_USE_WIV_CACHE_KEY", "True"
    ).lower() in ("true", "1")

    # AFTER_ACTION_SCRIPT_DEFAULT: Default for `script_options.after_action_script`.
    config["AFTER_ACTION_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_AFTER_ACTION_SCRIPT_DEFAULT", None
    )

    # POST_SCRIPT_DEFAULT: Default for `script_options.post_script`.
    config["POST_SCRIPT_DEFAULT"] = os.getenv("OFSC_POST_SCRIPT_DEFAULT", None)

    # ALERT_SCRIPT_DEFAULT: Default for `script_options.alert_script`.
    config["ALERT_SCRIPT_DEFAULT"] = os.getenv("OFSC_ALERT_SCRIPT_DEFAULT", None)

    # SKIP_DOWNLOAD_SCRIPT_DEFAULT: Default for `script_options.skip_download_script`.
    config["SKIP_DOWNLOAD_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_SKIP_DOWNLOAD_SCRIPT_DEFAULT", None
    )

    # AFTER_DOWNLOAD_SCRIPT_DEFAULT: Default for `script_options.after_download_script`.
    config["AFTER_DOWNLOAD_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_AFTER_DOWNLOAD_SCRIPT_DEFAULT", None
    )

    # ENV_FILES_DEFAULT: Defined but not read anywhere.
    config["ENV_FILES_DEFAULT"] = os.getenv("OFSC_ENV_FILES_DEFAULT", "")

    # SKIP_DOWNLOAD_SCRIPT_DEFAULT: Default for `script_options.skip_download_script`.
    config["SKIP_DOWNLOAD_SCRIPT_DEFAULT"] = os.getenv(
        "OFSC_SKIP_DOWNLOAD_SCRIPT_DEFAULT", None
    )

    # NAMING_SCRIPT_DEFAULT: Default for `script_options.naming_script`.
    config["NAMING_SCRIPT_DEFAULT"] = os.getenv("OFSC_NAMING_SCRIPT_DEFAULT", None)

    # DOWNLOAD_LIMIT_DEFAULT: Default for `performance_options.download_limit` (maximum download speed in bytes per second; 0 means unlimited).
    # Default: 0
    config["DOWNLOAD_LIMIT_DEFAULT"] = int(
        os.getenv("OFSC_DOWNLOAD_LIMIT_DEFAULT", "0")
    )

    # --- Format String Defaults (These are often user-configurable, but have internal defaults) ---
    # DIR_FORMAT_DEFAULT: Default for `file_options.dir_format`.
    # Default: "{model_username}/{responsetype}/{mediatype}/"
    config["DIR_FORMAT_DEFAULT"] = os.getenv(
        "OFSC_DIR_FORMAT_DEFAULT", "{model_username}/{responsetype}/{mediatype}/"
    )

    # FILE_FORMAT_DEFAULT: Default for `file_options.file_format`.
    # Default: "{filename}.{ext}"
    config["FILE_FORMAT_DEFAULT"] = os.getenv(
        "OFSC_FILE_FORMAT_DEFAULT", "{filename}.{ext}"
    )

    # METADATA_DEFAULT: Default for `metadata` (folder pattern for each creator's `user_data.db`).
    # Default: "{configpath}/{profile}/.data/{model_id}"
    config["METADATA_DEFAULT"] = os.getenv(
        "OFSC_METADATA_DEFAULT", "{configpath}/{profile}/.data/{model_id}"
    )

    # --- Complex Defaults (Better as Python Constants, not environment variables) ---
    # RESPONSE_TYPE_DEFAULT: Default for the `responsetype` map in `config.json` (accepts a JSON object via `OFSC_RESPONSE_TYPE_DEFAULT`).
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

    # EMPTY_MEDIA_DEFAULT: Defined but not read anywhere.
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

    # FILTER_DEFAULT: Default for `download_options.filter` (media types to download; accepts a comma-separated list via `OFSC_FILTER_DEFAULT`).
    # Default: ["Images", "Audios", "Videos"] (list of strings)
    # If provided via environment, expect comma-separated string, e.g., "Images,Videos"
    filter_default_env = os.getenv("OFSC_FILTER_DEFAULT")
    if filter_default_env:
        config["FILTER_DEFAULT"] = [f.strip() for f in filter_default_env.split(",")]
    else:
        config["FILTER_DEFAULT"] = ["Images", "Audios", "Videos"]

    ssl_verify = os.getenv("OFSC_SSL_VALIDATION_DEFAULT", "custom")
    config["SSL_VALIDATION_DEFAULT"] = ssl_verify

    return config
