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

    # DATAWHORES_URL: "https://raw.githubusercontent.com/datawhores/onlyfans-dynamic-rules/main/dynamicRules.json"
    # Environment variable: OF_DATAWHORES_URL
    config["DATAWHORES_URL"] = os.getenv(
        "OF_DATAWHORES_URL",
        "https://raw.githubusercontent.com/datawhores/onlyfans-dynamic-rules/main/dynamicRules.json",
    )

    # DEVIINT_URL: Dynamic rules URL for Deviint
    # Default: YOUR_DEVIINT_URL_HERE "https://raw.githubusercontent.com/deviint/onlyfans-dynamic-rules/main/dynamicRules.json"
    # Environment variable: OF_DEVIINT_URL
    config["DEVIINT_URL"] = os.getenv(
        "OF_DEVIINT_URL",
        "https://raw.githubusercontent.com/deviint/onlyfans-dynamic-rules/main/dynamicRules.json",
    )

    # RILEY_URL: Dynamic rules URL for Riley Access Labs
    # Default: https://raw.githubusercontent.com/riley-access-labs/onlyfans-dynamic-rules-1/refs/heads/main/dynamicRules.json
    # Environment variable: OF_RILEY_URL
    config["RILEY_URL"] = os.getenv(
        "OF_RILEY_URL",
        "https://raw.githubusercontent.com/riley-access-labs/onlyfans-dynamic-rules-1/refs/heads/main/dynamicRules.json",
    )

    # DYNAMIC_GENERIC_URL: None
    # Environment variable: OF_DYNAMIC_GENERIC_URL
    # Note: os.getenv returns None by default if the environment variable is not set
    config["DYNAMIC_GENERIC_URL"] = os.getenv("OF_DYNAMIC_GENERIC_URL", None)

    return config
