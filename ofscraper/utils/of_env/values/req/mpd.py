import os


def load_mpd_config():
    """
    Loads MPD (Media Presentation Description) related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded MPD configuration settings.
    """
    config = {}

    # --- MPD Configuration ---
    # MPD_CONNECT_TIMEOUT: Connection timeout, in seconds, when fetching DRM manifests (MPD).
    # Default: 45
    config["MPD_CONNECT_TIMEOUT"] = int(os.getenv("OFSC_MPD_CONNECT_TIMEOUT", "45"))

    # MPD_TOTAL_TIMEOUT: Total request timeout, in seconds, when fetching DRM manifests (MPD) (`None` means no limit).
    #
    # If set via environment, it will be an integer; otherwise, it remains None.
    mpd_total_timeout_env = os.getenv("OFSC_MPD_TOTAL_TIMEOUT", None)
    if mpd_total_timeout_env is not None:
        try:
            config["MPD_TOTAL_TIMEOUT"] = int(mpd_total_timeout_env)
        except ValueError:
            print(
                f"Warning: OFSC_MPD_TOTAL_TIMEOUT environment variable '{mpd_total_timeout_env}' is not a valid integer. Using default None."
            )
            config["MPD_TOTAL_TIMEOUT"] = None
    else:
        config["MPD_TOTAL_TIMEOUT"] = (
            None  # Explicitly set to None if not in env or invalid
        )

    # MPD_READ_TIMEOUT: Read timeout, in seconds, when fetching DRM manifests (MPD).
    # Default: 200
    config["MPD_READ_TIMEOUT"] = int(os.getenv("OFSC_MPD_READ_TIMEOUT", "200"))

    # MPD_POOL_CONNECT_TIMEOUT: Time, in seconds, allowed to get a connection when fetching DRM manifests (MPD).
    # Default: 45
    config["MPD_POOL_CONNECT_TIMEOUT"] = int(
        os.getenv("OFSC_MPD_POOL_CONNECT_TIMEOUT", "45")
    )

    # MPD_MAX_SEMS: Maximum concurrent requests when fetching DRM manifests (MPD).
    # Default: 10
    config["MPD_MAX_SEMS"] = int(os.getenv("OFSC_MPD_MAX_SEMS", "10"))

    # MPD_NUM_TRIES: Maximum number of attempts when fetching DRM manifests (MPD).
    # Default: 5
    config["MPD_NUM_TRIES"] = int(os.getenv("OFSC_MPD_NUM_TRIES", "5"))

    # MPD_SESSION_SLEEP_INIT: Time to sleep on mpd 429/504 errors.
    # Default: 45
    config["MPD_SESSION_SLEEP_INIT"] = int(
        os.getenv("OFSC_MPD_SESSION_SLEEP_INIT", "45")
    )
    return config
