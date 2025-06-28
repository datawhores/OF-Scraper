import os


def load_log_config():
    """
    Loads logging-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded logging configuration settings.
    """
    config = {}

    # --- Logging Configuration ---
    # LOGGER_TIMEOUT: Timeout for logger operations (seconds).
    # Default: 0.4
    config["LOGGER_TIMEOUT"] = float(os.getenv("OFSC_LOGGER_TIMEOUT", "0.4"))

    # LOG_DISPLAY_TIMEOUT: Timeout for log display updates (seconds).
    # Default: 0.8
    config["LOG_DISPLAY_TIMEOUT"] = float(os.getenv("OFSC_LOG_DISPLAY_TIMEOUT", "0.8"))

    # FORCED_THREAD_TIMEOUT: Timeout for forced thread termination in logging (seconds).
    # Default: 5
    config["FORCED_THREAD_TIMEOUT"] = int(os.getenv("OFSC_FORCED_THREAD_TIMEOUT", "5"))

    # logname: Base name for the logger.
    # Default: "ofscraper"
    config["logname"] = os.getenv("OFSC_LOGNAME", "ofscraper")

    return config
