import os


def load_system_config():
    """
    Loads subprocess logging configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded subprocess logging configuration settings.
    """
    config = {}

    ## --- Subprocess Log Level Configuration ---
    ## LOG LEVEL of 0 will disable that output
    # Set log level for user-defined scripts
    config["AFTER_DOWNLOAD_ACTION_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_AFTER_DOWNLOAD_ACTION_SCRIPT_SUBPROCESS_LEVEL", "20")
    )
    config["AFTER_LIKE_ACTION_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_AFTER_LIKE_ACTION_SCRIPT_SUBPROCESS_LEVEL", "20")
    )
    config["NAMING_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_NAMING_SCRIPT_SUBPROCESS_LEVEL", "20")
    )
    config["SKIP_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_SKIP_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL", "20")
    )
    config["AFTER_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_AFTER_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL", "20")
    )
    config["FINAL_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_FINAL_SCRIPT_SUBPROCESS_LEVEL", "20")
    )

    config["LOG_SUBPROCESS_LEVEL"] = int(os.getenv("OFSC_LOG_SUBPROCESS_LEVELL", "10"))

    # Set log level for FFmpeg operations
    config["FFMPEG_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_FFMPEG_SUBPROCESS_LEVEL", "0")
    )

    # Free Space
    config["DISK_SPACE_CHECK_PATH"] = os.getenv("OFSC_DISK_SPACE_CHECK_PATH", "/")

    return config
