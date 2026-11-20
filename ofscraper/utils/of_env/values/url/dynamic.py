import os


def load_dynamic_url_config():
    """
    Loads dynamic rule URLs from environment variables with default values.

    Returns:
        A dictionary containing all loaded dynamic rule URLs.
    """
    config = {}
    # XAGLER_URL: "https://raw.githubusercontent.com/xagler/dynamic-rules/main/onlyfans.json"
    # Environment variable: OF_XAGLER_URL
    config["XAGLER_URL"] = os.getenv(
        "OF_XAGLER_URL",
        "https://raw.githubusercontent.com/xagler/dynamic-rules/main/onlyfans.json",
    )

    # RAFA_URL: "https://raw.githubusercontent.com/rafa-9/dynamic-rules/main/rules.json"
    # Environment variable: OF_RAFA_URL
    config["RAFA_URL"] = os.getenv(
        "OF_RAFA_URL",
        "https://raw.githubusercontent.com/rafa-9/dynamic-rules/main/rules.json",
    )

    # DIGITALCRIMINALS: "https://raw.githubusercontent.com/DATAHOARDERS/dynamic-rules/main/onlyfans.json"
    # Environment variable: OF_DIGITALCRIMINALS_URL (added _URL for consistency)
    config["DIGITALCRIMINALS"] = os.getenv(
        "OF_DIGITALCRIMINALS_URL",
        "https://raw.githubusercontent.com/DATAHOARDERS/dynamic-rules/main/onlyfans.json",
    )

    # DYNAMIC_GENERIC_URL: None
    # Environment variable: OF_DYNAMIC_GENERIC_URL
    # Note: os.getenv returns None by default if the environment variable is not set
    config["DYNAMIC_GENERIC_URL"] = os.getenv("OF_DYNAMIC_GENERIC_URL", None)

    return config
