import os


def load_rich_config():
    """
    Loads refresh and flush related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded refresh/flush configuration settings.
    """
    config = {}

    # --- Refresh and Flush Configuration ---
    # MULTIPROCESS_REFRESH_SECS: Refresh interval for multiprocess operations (seconds).
    # Default: 1
    config["MULTIPROCESS_REFRESH_SECS"] = int(
        os.getenv("OFSC_MULTIPROCESS_REFRESH_SECS", "1")
    )

    # DEFAULT_FLUSH_MAX: Default maximum number of items to flush.
    # Default: 100
    config["DEFAULT_FLUSH_MAX"] = int(os.getenv("OFSC_DEFAULT_FLUSH_MAX", "100"))

    # CLOSING_FLUSH_MAX: Maximum number of items to flush during closing procedures.
    # Default: 150
    config["CLOSING_FLUSH_MAX"] = int(os.getenv("OFSC_CLOSING_FLUSH_MAX", "150"))

    return config
