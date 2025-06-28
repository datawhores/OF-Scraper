import os


def load_live_display_config():
    """
    Loads live display and suppression settings from environment variables with default values.

    Returns:
        A dictionary containing all loaded live display configuration settings.
    """
    config = {}

    # --- Live Display Configuration ---
    # SUPRESS_API_DISPLAY: Whether to suppress API display messages. Defaults to None.
    # If set via environment, it will be a string; otherwise, it remains None.
    config["SUPRESS_API_DISPLAY"] = os.getenv("OFSC_SUPRESS_API_DISPLAY", None)

    # SUPRESS_DOWNLOAD_DISPLAY: Whether to suppress download display messages. Defaults to None.
    # If set via environment, it will be a string; otherwise, it remains None.
    config["SUPRESS_DOWNLOAD_DISPLAY"] = os.getenv(
        "OFSC_SUPRESS_DOWNLOAD_DISPLAY", None
    )

    # SUPRESS_SUBSCRIPTION_DISPLAY: Whether to suppress subscription display messages. Defaults to None.
    # If set via environment, it will be a string; otherwise, it remains None.
    config["SUPRESS_SUBSCRIPTION_DISPLAY"] = os.getenv(
        "OFSC_SUPRESS_SUBSCRIPTION_DISPLAY", None
    )

    # SUPRESS_LIKE_DISPLAY: Whether to suppress like display messages. Defaults to None.
    # If set via environment, it will be a string; otherwise, it remains None.
    config["SUPRESS_LIKE_DISPLAY"] = os.getenv("OFSC_SUPRESS_LIKE_DISPLAY", None)

    # DOWNLOAD_LIVE_DISPLAY: Whether to enable live download progress display.
    # Default: True
    config["DOWNLOAD_LIVE_DISPLAY"] = os.getenv(
        "OFSC_DOWNLOAD_LIVE_DISPLAY", "True"
    ).lower() in ("true", "1")

    return config
