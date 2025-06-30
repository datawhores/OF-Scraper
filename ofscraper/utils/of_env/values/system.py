import os


def load_system_config():
    """
    Loads subprocess logging configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded subprocess logging configuration settings.
    """
    config = {}

    # --- Subprocess Logging Configuration ---
    # LOG_SUBPROCESS: Whether to log subprocess activity.
    # Takes precidence over all other output changes
    # Default: False
    config["LOG_SUBPROCESS"] = os.getenv("OFSC_LOG_SUBPROCESS", "True").lower() in (
        "true",
        "1",
    )

    # FFMPEG_OUTPUT_SUBPROCCESS: Whether to log ffmpeg messages.
    # Default: None
    config["FFMPEG_OUTPUT_SUBPROCCESS"] = os.getenv(
        "OFSC_FFMPEG_OUTPUT_SUBPROCCESS", "False"
    ).lower() in (
        "true",
        "1",
    )

    # "SCRIPT_OUTPUT_SUBPROCCESS: Whether to log general script messages.
    # Default: None
    config["SCRIPT_OUTPUT_SUBPROCCESS"] = os.getenv(
        "OFSC_SCRIPT_OUTPUT_SUBPROCCESS", "True"
    ).lower() in (
        "true",
        "1",
    )

    return config
