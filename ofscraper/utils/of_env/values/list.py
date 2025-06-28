import os


def load_list_config():
    """
    Loads list-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded list configuration settings.
    """
    config = {}

    # --- List Configuration ---
    # OFSCRAPER_RESERVED_LIST: Reserved list identifier for Ofscraper.
    # Default: "ofscraper.main"
    config["OFSCRAPER_RESERVED_LIST"] = os.getenv(
        "OFSCRAPER_RESERVED_LIST", "ofscraper.main"
    )

    # OFSCRAPER_RESERVED_LIST_ALT: Alternative reserved list identifier.
    # Default: "main"
    config["OFSCRAPER_RESERVED_LIST_ALT"] = os.getenv(
        "OFSCRAPER_RESERVED_LIST_ALT", "main"
    )

    # OFSCRAPER_ACTIVE_LIST: Active list identifier for Ofscraper.
    # Default: "ofscraper.active"
    config["OFSCRAPER_ACTIVE_LIST"] = os.getenv(
        "OFSCRAPER_ACTIVE_LIST", "ofscraper.active"
    )

    # OFSCRAPER_ACTIVE_LIST_ALT: Alternative active list identifier.
    # Default: "active"
    config["OFSCRAPER_ACTIVE_LIST_ALT"] = os.getenv(
        "OFSCRAPER_ACTIVE_LIST_ALT", "active"
    )

    # OFSCRAPER_EXPIRED_LIST: Expired list identifier for Ofscraper.
    # Default: "ofscraper.expired"
    config["OFSCRAPER_EXPIRED_LIST"] = os.getenv(
        "OFSCRAPER_EXPIRED_LIST", "ofscraper.expired"
    )

    # OFSCRAPER_EXPIRED_LIST_ALT: Alternative expired list identifier.
    # Default: "expired"
    config["OFSCRAPER_EXPIRED_LIST_ALT"] = os.getenv(
        "OFSCRAPER_EXPIRED_LIST_ALT", "expired"
    )

    return config
