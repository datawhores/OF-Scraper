import os


def load_discord_config():
    """
    Loads Discord-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded Discord configuration settings.
    """
    config = {}

    # --- Discord Configuration ---
    # DISCORD_TOTAL_TIMEOUT: Total timeout for Discord operations (seconds). Defaults to None.
    # If set via environment, it will be an integer; otherwise, it remains None.
    discord_total_timeout_env = os.getenv("OFSC_DISCORD_TOTAL_TIMEOUT", None)
    if discord_total_timeout_env is not None:
        try:
            config["DISCORD_TOTAL_TIMEOUT"] = int(discord_total_timeout_env)
        except ValueError:
            print(
                f"Warning: OFSC_DISCORD_TOTAL_TIMEOUT environment variable '{discord_total_timeout_env}' is not a valid integer. Using default None."
            )
            config["DISCORD_TOTAL_TIMEOUT"] = None
    else:
        config["DISCORD_TOTAL_TIMEOUT"] = (
            None  # Explicitly set to None if not in env or invalid
        )

    # DISCORD_MIN_WAIT: Minimum wait time for Discord operations (seconds).
    # Default: 1
    config["DISCORD_MIN_WAIT"] = float(os.getenv("OFSC_DISCORD_MIN_WAIT", "1"))

    # DISCORD_MAX_WAIT: Maximum wait time for Discord operations (seconds).
    # Default: 5
    config["DISCORD_MAX_WAIT"] = float(os.getenv("OFSC_DISCORD_MAX_WAIT", "5"))

    # DISCORD_NUM_TRIES: Number of retries for Discord operations.
    # Default: 3
    config["DISCORD_NUM_TRIES"] = int(os.getenv("OFSC_DISCORD_NUM_TRIES", "3"))

    return config
