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
    # Default: False
    config["LOG_SUBPROCESS"] = os.getenv("OFSC_LOG_SUBPROCESS", "False").lower() in (
        "true",
        "1",
    )

    # LOG_SUBPROCESS_LEVEL: Log level for subprocess messages.
    # Default: 100 (likely a custom level indicating very high verbosity or a specific type of message)
    config["LOG_SUBPROCESS_LEVEL"] = int(os.getenv("OFSC_LOG_SUBPROCESS_LEVEL", "100"))

    return config
