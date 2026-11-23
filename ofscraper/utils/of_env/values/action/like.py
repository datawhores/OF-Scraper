import os


def load_like_config():
    """
    Loads 'like' related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded 'like' configuration settings.
    """
    config = {}

    # --- Like Feature Configuration ---
    # MAX_SLEEP_DURATION_LIKE: Upper bound, in seconds, of the random pause between like or unlike requests (and before retrying an already-liked post).
    # Default: 3.5
    config["MAX_SLEEP_DURATION_LIKE"] = float(
        os.getenv("MAX_SLEEP_DURATION_LIKE", "3.5")
    )

    # MIN_SLEEP_DURATION_LIKE: Lower bound, in seconds, of the random pause between like or unlike requests (and before retrying an already-liked post).
    # Default: 0.9
    config["MIN_SLEEP_DURATION_LIKE"] = float(
        os.getenv("MIN_SLEEP_DURATION_LIKE", ".9")
    )

    # LIKE_MAX_RETRIES: Maximum number of attempts for a failed like or unlike request.
    # Default: 5
    config["LIKE_MAX_RETRIES"] = int(os.getenv("LIKE_MAX_RETRIES", "5"))

    # DOUBLE_TOGGLE_SLEEP_DURATION_LIKE: Pause, in seconds, before sending a second unlike request when a post was already unliked and toggled to liked.
    # Default: 5
    config["DOUBLE_TOGGLE_SLEEP_DURATION_LIKE"] = int(
        os.getenv("DOUBLE_TOGGLE_SLEEP_DURATION_LIKE", "5")
    )

    return config
