import os


def load_file_paths_config():
    """
    Loads file paths configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded file paths configuration settings.
    """
    config = {}

    # --- File Paths Configuration ---
    # preferences: Defined but not read anywhere.
    # Default: "pref_config.py"
    config["preferences"] = os.getenv("OFSC_PREFERENCES_FILE", "pref_config.py")

    # configPath: Folder relative to the home directory where `config.json` and profiles live.
    # Default: ".config/ofscraper"
    config["configPath"] = os.getenv("OFSC_CONFIG_DIR", ".config/ofscraper")

    # configFile: Name of the main configuration file inside the config folder.
    # Default: "config.json"
    config["configFile"] = os.getenv("OFSC_CONFIG_FILE_NAME", "config.json")

    # authFile: Name of the OnlyFans credentials file inside the profile folder.
    # Default: "auth.json"
    config["authFile"] = os.getenv("OFSC_AUTH_FILE_NAME", "auth.json")

    # databaseFile: Defined but not read anywhere.
    # Default: "models.db"
    config["databaseFile"] = os.getenv("OFSC_DATABASE_FILE_NAME", "models.db")

    # mainProfile: Key name in `config.json` that stores the default profile name.
    # Default: "main_profile"
    config["mainProfile"] = os.getenv("OFSC_MAIN_PROFILE_NAME", "main_profile")

    # requestAuth: Defined but not read anywhere.
    # Default: "request_auth.json"
    config["requestAuth"] = os.getenv(
        "OFSC_REQUEST_AUTH_FILE_NAME", "request_auth.json"
    )

    return config
