import os


def load_expiry_config():
    """
    Loads various expiry and timeout configurations from environment variables with default values.

    Returns:
        A dictionary containing all loaded expiry/timeout configuration settings.
    """
    config = {}

    # --- Expiry and Timeout Configuration ---
    # HOURLY_EXPIRY: Defined but not read anywhere.
    # Default: 3600 (1 hour)
    config["HOURLY_EXPIRY"] = int(os.getenv("OFSC_HOURLY_EXPIRY", "3600"))

    # THIRTY_EXPIRY: Cache lifetime, in seconds, for OnlyFans dynamic signing rules.
    # Default: 1800 (30 minutes)
    config["THIRTY_EXPIRY"] = int(os.getenv("OFSC_THIRTY_EXPIRY", "1800"))

    # SIZE_TIMEOUT: Defined but not read anywhere.
    # Default: 1209600 (2 weeks)
    config["SIZE_TIMEOUT"] = int(os.getenv("OFSC_SIZE_TIMEOUT", "1209600"))

    # DATABASE_TIMEOUT: Timeout, in seconds, for SQLite and PostgreSQL database locks and connections.
    # Default: 300 (5 minutes)
    config["DATABASE_TIMEOUT"] = int(os.getenv("OFSC_DATABASE_TIMEOUT", "300"))

    # KEY_EXPIRY: Cache lifetime, in seconds, for Widevine decryption keys (`None` means no expiry).
    key_expiry_env = os.getenv("OFSC_KEY_EXPIRY", None)
    if key_expiry_env is not None:
        try:
            config["KEY_EXPIRY"] = int(key_expiry_env)
        except ValueError:
            print(
                f"Warning: OFSC_KEY_EXPIRY environment variable '{key_expiry_env}' is not a valid integer. Using default None."
            )
            config["KEY_EXPIRY"] = None
    else:
        config["KEY_EXPIRY"] = None

    # RESPONSE_EXPIRY: Cache lifetime, in seconds, for scraped paid-page responses.
    # Default: 5000000
    config["RESPONSE_EXPIRY"] = int(os.getenv("OFSC_RESPONSE_EXPIRY", "5000000"))

    # DBINTERVAL: Minimum time, in seconds, between rotating `user_data_copy_N.db` backups.
    # Default: 86400 (1 day)
    config["DBINTERVAL"] = int(os.getenv("OFSC_DBINTERVAL", "86400"))

    # DAY_SECONDS: Cache lifetime, in seconds, for username-to-model-ID lookups.
    # Default: 86400
    config["DAY_SECONDS"] = int(os.getenv("OFSC_DAY_SECONDS", "86400"))

    # THREE_DAY_SECONDS: Cache lifetime, in seconds, for check-mode API caches.
    # Default: 259200 (DAY_SECONDS * 3)
    config["THREE_DAY_SECONDS"] = int(
        os.getenv("OFSC_THREE_DAY_SECONDS", str(86400 * 3))
    )

    # PROFILE_DATA_EXPIRY: Cache lifetime, in seconds, for synchronous creator profile lookups.
    # Default: 86400 (1 day)
    config["PROFILE_DATA_EXPIRY"] = int(os.getenv("OFSC_PROFILE_DATA_EXPIRY", "86400"))

    # PROFILE_DATA_EXPIRY_ASYNC: Cache lifetime, in seconds, for async creator profile lookups.
    # Default: 86400 (1 day)
    config["PROFILE_DATA_EXPIRY_ASYNC"] = int(
        os.getenv("OFSC_PROFILE_DATA_EXPIRY_ASYNC", "86400")
    )

    return config
