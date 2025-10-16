import os


def load_dynamic_rules_config():
    """
    Loads dynamic rules configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded dynamic rules configuration settings.
    """
    config = {}

    # --- Dynamic Rules Configuration ---
    # DYNAMIC_RULE_MANUAL: The specific manual dynamic rule to use. Defaults to None.
    config["DYNAMIC_RULE_MANUAL"] = os.getenv("OFSC_DYNAMIC_RULE_MANUAL", None)

    # DYNAMIC_OPTIONS: List of available dynamic rule options.
    # Default: ["digitalcriminals", "manual", "generic", "xagler", "rafa", "datawhores"]
    dynamic_options_env = os.getenv("OFSC_DYNAMIC_OPTIONS")
    if dynamic_options_env:
        config["DYNAMIC_OPTIONS"] = [
            opt.strip() for opt in dynamic_options_env.split(",")
        ]
    else:
        config["DYNAMIC_OPTIONS"] = [
            "manual",
            "generic",
            "xagler",
            "rafa",
            "datawhores",
        ]

    # DYNAMIC_OPTIONS_ALL: Comprehensive list of all dynamic rule options including aliases.
    # This list is derived from DYNAMIC_OPTIONS, so it should be built after DYNAMIC_OPTIONS is set.
    dynamic_options_all_env = os.getenv("OFSC_DYNAMIC_OPTIONS_ALL")
    if dynamic_options_all_env:
        config["DYNAMIC_OPTIONS_ALL"] = [
            opt.strip() for opt in dynamic_options_all_env.split(",")
        ]
    else:
        # Build default from base DYNAMIC_OPTIONS plus hardcoded aliases
        config["DYNAMIC_OPTIONS_ALL"] = config["DYNAMIC_OPTIONS"] + [
            "digitalcriminals",
            "dv",
            "dev",
            "dc",
            "digital",
            "digitals",
            "manual",
            "generic",
        ]

    # DYNAMIC_RULE_DEFAULT: The default dynamic rule when none is specified.
    # Default: "rafa"
    config["DYNAMIC_RULE_DEFAULT"] = os.getenv("OFSC_DYNAMIC_RULE_DEFAULT", "rafa")

    return config
