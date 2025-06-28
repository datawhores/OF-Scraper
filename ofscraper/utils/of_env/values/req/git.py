import os


def load_git_config():
    """
    Loads Git-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded Git configuration settings.
    """
    config = {}

    # --- Git Configuration ---
    # GIT_MIN_WAIT: Minimum wait time before retrying a Git operation (seconds).
    # Default: 1
    config["GIT_MIN_WAIT"] = float(os.getenv("OFSC_GIT_MIN_WAIT", "1"))

    # GIT_MAX_WAIT: Maximum wait time before retrying a Git operation (seconds).
    # Default: 5
    config["GIT_MAX_WAIT"] = float(os.getenv("OFSC_GIT_MAX_WAIT", "5"))

    # GIT_NUM_TRIES: Number of retries for Git operations.
    # Default: 3
    config["GIT_NUM_TRIES"] = int(os.getenv("OFSC_GIT_NUM_TRIES", "3"))

    return config
