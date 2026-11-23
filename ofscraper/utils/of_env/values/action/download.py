import os


def load_download_config():
    """
    Loads application configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded configuration settings.
    """
    config = {}

    # --- File and Path Configuration ---
    # MAXFILE_SEMAPHORE: Overrides `performance_options.download_sems` as the maximum number of concurrent downloads. When unset, `download_sems` is used.
    config["MAXFILE_SEMAPHORE"] = os.getenv("MAXFILE_SEMAPHORE", None)
    if config["MAXFILE_SEMAPHORE"] is not None:
        try:
            config["MAXFILE_SEMAPHORE"] = int(config["MAXFILE_SEMAPHORE"])
        except ValueError:
            print(
                f"Warning: MAXFILE_SEMAPHORE environment variable '{os.getenv('MAXFILE_SEMAPHORE')}' is not a valid integer. Using default None."
            )
            config["MAXFILE_SEMAPHORE"] = None

    # PATH_STR_MAX: Maximum length of the file path shown on each download's progress bar before it is shortened (with `....`).
    # Default: 200
    config["PATH_STR_MAX"] = int(os.getenv("PATH_STR_MAX", "200"))

    # TABLE_STR_MAX: Read only by `texthelper()` in `commands/check.py`, which nothing calls, so it has no effect.
    # Default: 100
    config["TABLE_STR_MAX"] = int(os.getenv("TABLE_STR_MAX", "100"))

    # --- Download Configuration ---
    # SPACE_DOWNLOAD_MESSAGE: Error message raised when free disk space drops below `system_free_min`. The retry handler also matches this string so the download isn't retried.
    # Default: "Skipping download because space min has been reached"
    config["SPACE_DOWNLOAD_MESSAGE"] = os.getenv(
        "SPACE_DOWNLOAD_MESSAGE", "Skipping download because space min has been reached"
    )

    # DOWNLOAD_THREAD_MIN: Defined but not read anywhere.
    # Default: 35
    config["DOWNLOAD_THREAD_MIN"] = int(os.getenv("DOWNLOAD_THREAD_MIN", "35"))

    # DOWNLOAD_NUM_TRIES: Maximum number of download attempts outside check mode.
    # Default: 3
    config["DOWNLOAD_NUM_TRIES"] = int(os.getenv("DOWNLOAD_NUM_TRIES", "3"))

    # DOWNLOAD_NUM_TRIES_CHECK: Maximum number of download attempts in check mode (`*_check` commands).
    # Default: 3
    config["DOWNLOAD_NUM_TRIES_CHECK"] = int(os.getenv("DOWNLOAD_NUM_TRIES_CHECK", "3"))

    # --- Progress Bar Configuration ---
    # MAX_PROGRESS_BARS: Defined but not read anywhere.
    # Default: 60
    config["MAX_PROGRESS_BARS"] = int(os.getenv("MAX_PROGRESS_BARS", "60"))

    # MIN_ADD_PROGRESS_BARS: Defined but not read anywhere.
    # Default: 40
    config["MIN_ADD_PROGRESS_BARS"] = int(os.getenv("MIN_ADD_PROGRESS_BARS", "40"))

    # SHOW_DL_CHUNKS: When on, logs download chunk progress at `SHOW_DL_CHUNKS_LEVEL` instead of `TRACE`.
    # Default: False
    config["SHOW_DL_CHUNKS"] = os.getenv("SHOW_DL_CHUNKS", "False").lower() == "true"

    # SHOW_DL_CHUNKS_LEVEL: Log level used for download chunk progress messages when `SHOW_DL_CHUNKS` is on.
    # Default: "Warning"
    config["SHOW_DL_CHUNKS_LEVEL"] = os.getenv("SHOW_DL_CHUNKS_LEVEL", "Warning")

    # MULTIPROGRESS_JOB_UPDATE_FREQ: Defined but not read anywhere.
    # Default: 1.5
    config["MULTIPROGRESS_JOB_UPDATE_FREQ"] = float(
        os.getenv("MULTIPROGRESS_JOB_UPDATE_FREQ", "1.5")
    )

    # PROGRESS_JOB_UPDATE_FREQ: Defined but not read anywhere.
    # Default: 2.5
    config["PROGRESS_JOB_UPDATE_FREQ"] = float(
        os.getenv("PROGRESS_JOB_UPDATE_FREQ", "2.5")
    )

    # OVERALL_MULTI_PROGRESS_THREAD_SLEEP: Defined but not read anywhere.
    # Default: 0.1
    config["OVERALL_MULTI_PROGRESS_THREAD_SLEEP"] = float(
        os.getenv("OVERALL_MULTI_PROGRESS_THREAD_SLEEP", "0.1")
    )

    # JOB_MULTI_PROGRESS_THREAD_SLEEP: Defined but not read anywhere.
    # Default: 0.1
    config["JOB_MULTI_PROGRESS_THREAD_SLEEP"] = float(
        os.getenv("JOB_MULTI_PROGRESS_THREAD_SLEEP", "0.1")
    )

    # --- Force Key Configuration (Booleans) ---
    # CDM_FORCE_KEY: Defined but not read anywhere.
    # Default: True
    config["CDM_FORCE_KEY"] = os.getenv("CDM_FORCE_KEY", "True").lower() == "true"

    # META_FORCE_KEY: Defined but not read anywhere.
    # Default: True
    config["META_FORCE_KEY"] = os.getenv("META_FORCE_KEY", "True").lower() == "true"

    # DOWNLOAD_FORCE_KEY: Defined but not read anywhere.
    # Default: True
    config["DOWNLOAD_FORCE_KEY"] = (
        os.getenv("DOWNLOAD_FORCE_KEY", "True").lower() == "true"
    )

    # MPD_FORCE_KEY: Defined but not read anywhere.
    # Default: True
    config["MPD_FORCE_KEY"] = os.getenv("MPD_FORCE_KEY", "True").lower() == "true"

    # API_FORCE_KEY: Adds the `FORCED_NEW` action to OnlyFans API, download and metadata requests. Currently has no effect: request signing ignores that action.
    # Default: False
    config["API_FORCE_KEY"] = os.getenv("API_FORCE_KEY", "False").lower() == "true"

    # PROFILE_FORCE_KEY: Defined but not read anywhere.
    # Default: False
    config["PROFILE_FORCE_KEY"] = (
        os.getenv("PROFILE_FORCE_KEY", "False").lower() == "true"
    )
    # VERIFY_ALL_INTEGRITY: Default for `download_options.verify_all_integrity` (checks non-DRM video/audio downloads and Fansly streams with `ffprobe`).
    # Default: False
    config["VERIFY_ALL_INTEGRITY"] = os.getenv(
        "OFSC_VERIFY_ALL_INTEGRITY", "False"
    ).lower() in ("true", "1")
    return config
