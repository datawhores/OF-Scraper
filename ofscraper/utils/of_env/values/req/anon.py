import os


def load_req_config():
    """
    Loads request-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded request configuration settings.
    """
    config = {}

    # --- Request Configuration ---
    # ANON_USERAGENT: User-Agent string for anonymous requests.
    # Default: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    config["ANON_USERAGENT"] = os.getenv(
        "OFSC_ANON_USERAGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    )

    return config
