import os


def load_like_config():
    """
    Loads 'like' related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded 'like' configuration settings.
    """
    config = {}

    # --- Like Feature Configuration ---
    # MAX_SLEEP_DURATION_LIKE: Maximum sleep duration for like operations (seconds)
    # Default: 3.5
    config["MAX_SLEEP_DURATION_LIKE"] = float(
        os.getenv("MAX_SLEEP_DURATION_LIKE", "3.5")
    )

    # MIN_SLEEP_DURATION_LIKE: Minimum sleep duration for like operations (seconds)
    # Default: 0.9
    config["MIN_SLEEP_DURATION_LIKE"] = float(
        os.getenv("MIN_SLEEP_DURATION_LIKE", ".9")
    )

    # LIKE_MAX_RETRIES: Maximum number of retries for failed like operations
    # Default: 5
    config["LIKE_MAX_RETRIES"] = int(os.getenv("LIKE_MAX_RETRIES", "5"))

    # DOUBLE_TOGGLE_SLEEP_DURATION_LIKE: Sleep duration in seconds for double toggle like operations
    # Default: 5
    config["DOUBLE_TOGGLE_SLEEP_DURATION_LIKE"] = int(
        os.getenv("DOUBLE_TOGGLE_SLEEP_DURATION_LIKE", "5")
    )

    return config
