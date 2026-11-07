import os

# Switches that stay None when unset: the display then follows the output
# options. of_env.getattr converts a bare-key value of these to bool too.
OPTIONAL_BOOLS = {
    "SUPRESS_API_DISPLAY",
    "SUPRESS_DOWNLOAD_DISPLAY",
    "SUPRESS_SUBSCRIPTION_DISPLAY",
    "SUPRESS_LIKE_DISPLAY",
}


def _optional_bool(value):
    # environment values are text, and "False" is truthy
    return None if value is None else value.strip().lower() in ("true", "1")


def load_live_display_config():
    """
    Loads live display and suppression settings from environment variables with default values.

    Returns:
        A dictionary containing all loaded live display configuration settings.
    """
    config = {}

    # --- Live Display Configuration ---
    # SUPRESS_API_DISPLAY: Whether to suppress API display messages. Defaults to None.
    # If set via environment, it's True for "true" or "1" and False otherwise; unset, it remains None.
    config["SUPRESS_API_DISPLAY"] = _optional_bool(
        os.getenv("OFSC_SUPRESS_API_DISPLAY")
    )

    # SUPRESS_DOWNLOAD_DISPLAY: Whether to suppress download display messages. Defaults to None.
    # If set via environment, it's True for "true" or "1" and False otherwise; unset, it remains None.
    config["SUPRESS_DOWNLOAD_DISPLAY"] = _optional_bool(
        os.getenv("OFSC_SUPRESS_DOWNLOAD_DISPLAY")
    )

    # SUPRESS_SUBSCRIPTION_DISPLAY: Whether to suppress subscription display messages. Defaults to None.
    # If set via environment, it's True for "true" or "1" and False otherwise; unset, it remains None.
    config["SUPRESS_SUBSCRIPTION_DISPLAY"] = _optional_bool(
        os.getenv("OFSC_SUPRESS_SUBSCRIPTION_DISPLAY")
    )

    # SUPRESS_LIKE_DISPLAY: Whether to suppress like display messages. Defaults to None.
    # If set via environment, it's True for "true" or "1" and False otherwise; unset, it remains None.
    config["SUPRESS_LIKE_DISPLAY"] = _optional_bool(os.getenv("OFSC_SUPRESS_LIKE_DISPLAY"))

    # DOWNLOAD_LIVE_DISPLAY: Whether to enable live download progress display.
    # Default: True
    config["DOWNLOAD_LIVE_DISPLAY"] = os.getenv(
        "OFSC_DOWNLOAD_LIVE_DISPLAY", "True"
    ).lower() in ("true", "1")

    return config
