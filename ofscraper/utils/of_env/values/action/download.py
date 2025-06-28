import os


def load_download_config():
    """
    Loads application configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded configuration settings.
    """
    config = {}

    # --- File and Path Configuration ---
    # MAXFILE_SEMAPHORE: If not set in environment, defaults to None
    config["MAXFILE_SEMAPHORE"] = os.getenv("MAXFILE_SEMAPHORE", None)
    if config["MAXFILE_SEMAPHORE"] is not None:
        try:
            config["MAXFILE_SEMAPHORE"] = int(config["MAXFILE_SEMAPHORE"])
        except ValueError:
            print(
                f"Warning: MAXFILE_SEMAPHORE environment variable '{os.getenv('MAXFILE_SEMAPHORE')}' is not a valid integer. Using default None."
            )
            config["MAXFILE_SEMAPHORE"] = None

    # PATH_STR_MAX: Maximum length for path strings
    # Default: 200
    config["PATH_STR_MAX"] = int(os.getenv("PATH_STR_MAX", "200"))

    # TABLE_STR_MAX: Maximum length for table strings
    # Default: 100
    config["TABLE_STR_MAX"] = int(os.getenv("TABLE_STR_MAX", "100"))

    # --- Download Configuration ---
    # SPACE_DOWNLOAD_MESSAGE: Message for skipping download due to low space
    # Default: "Skipping download because space min has been reached"
    config["SPACE_DOWNLOAD_MESSAGE"] = os.getenv(
        "SPACE_DOWNLOAD_MESSAGE", "Skipping download because space min has been reached"
    )

    # DOWNLOAD_THREAD_MIN: Minimum number of download threads
    # Default: 35
    config["DOWNLOAD_THREAD_MIN"] = int(os.getenv("DOWNLOAD_THREAD_MIN", "35"))

    # DOWNLOAD_NUM_TRIES: Number of times to retry a download
    # Default: 3
    config["DOWNLOAD_NUM_TRIES"] = int(os.getenv("DOWNLOAD_NUM_TRIES", "3"))

    # DOWNLOAD_NUM_TRIES_CHECK: Number of times to check download status
    # Default: 3
    config["DOWNLOAD_NUM_TRIES_CHECK"] = int(os.getenv("DOWNLOAD_NUM_TRIES_CHECK", "3"))

    # --- Progress Bar Configuration ---
    # MAX_PROGRESS_BARS: Maximum number of progress bars to display
    # Default: 60
    config["MAX_PROGRESS_BARS"] = int(os.getenv("MAX_PROGRESS_BARS", "60"))

    # MIN_ADD_PROGRESS_BARS: Minimum number of progress bars to add
    # Default: 40
    config["MIN_ADD_PROGRESS_BARS"] = int(os.getenv("MIN_ADD_PROGRESS_BARS", "40"))

    # SHOW_DL_CHUNKS: Show download chunks in progress bars (boolean)
    # Default: False
    config["SHOW_DL_CHUNKS"] = os.getenv("SHOW_DL_CHUNKS", "False").lower() == "true"

    # SHOW_DL_CHUNKS_LEVEL: Level for showing download chunks messages
    # Default: "Warning"
    config["SHOW_DL_CHUNKS_LEVEL"] = os.getenv("SHOW_DL_CHUNKS_LEVEL", "Warning")

    # MULTIPROGRESS_JOB_UPDATE_FREQ: Update frequency for multiprogress jobs (seconds)
    # Default: 1.5
    config["MULTIPROGRESS_JOB_UPDATE_FREQ"] = float(
        os.getenv("MULTIPROGRESS_JOB_UPDATE_FREQ", "1.5")
    )

    # PROGRESS_JOB_UPDATE_FREQ: Update frequency for single progress jobs (seconds)
    # Default: 2.5
    config["PROGRESS_JOB_UPDATE_FREQ"] = float(
        os.getenv("PROGRESS_JOB_UPDATE_FREQ", "2.5")
    )

    # OVERALL_MULTI_PROGRESS_THREAD_SLEEP: Sleep time for overall multi-progress thread (seconds)
    # Default: 0.1
    config["OVERALL_MULTI_PROGRESS_THREAD_SLEEP"] = float(
        os.getenv("OVERALL_MULTI_PROGRESS_THREAD_SLEEP", "0.1")
    )

    # JOB_MULTI_PROGRESS_THREAD_SLEEP: Sleep time for individual job multi-progress thread (seconds)
    # Default: 0.1
    config["JOB_MULTI_PROGRESS_THREAD_SLEEP"] = float(
        os.getenv("JOB_MULTI_PROGRESS_THREAD_SLEEP", "0.1")
    )

    # --- Force Key Configuration (Booleans) ---
    # CDM_FORCE_KEY: Force CDM Key
    # Default: True
    config["CDM_FORCE_KEY"] = os.getenv("CDM_FORCE_KEY", "True").lower() == "true"

    # META_FORCE_KEY: Force Meta Key
    # Default: True
    config["META_FORCE_KEY"] = os.getenv("META_FORCE_KEY", "True").lower() == "true"

    # DOWNLOAD_FORCE_KEY: Force Download Key
    # Default: True
    config["DOWNLOAD_FORCE_KEY"] = (
        os.getenv("DOWNLOAD_FORCE_KEY", "True").lower() == "true"
    )

    # MPD_FORCE_KEY: Force MPD Key
    # Default: True
    config["MPD_FORCE_KEY"] = os.getenv("MPD_FORCE_KEY", "True").lower() == "true"

    # API_FORCE_KEY: Force API Key
    # Default: False
    config["API_FORCE_KEY"] = os.getenv("API_FORCE_KEY", "False").lower() == "true"

    # PROFILE_FORCE_KEY: Force Profile Key
    # Default: False
    config["PROFILE_FORCE_KEY"] = (
        os.getenv("PROFILE_FORCE_KEY", "False").lower() == "true"
    )

    return config
