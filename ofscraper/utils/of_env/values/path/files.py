import os


def load_file_paths_config():
    """
    Loads file paths configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded file paths configuration settings.
    """
    config = {}

    # --- File Paths Configuration ---
    # preferences: Name of the preferences configuration file
    # Default: "pref_config.py"
    config["preferences"] = os.getenv("OFSC_PREFERENCES_FILE", "pref_config.py")

    # configPath: Base directory for configuration files
    # Default: ".config/ofscraper"
    config["configPath"] = os.getenv("OFSC_CONFIG_DIR", ".config/ofscraper")

    # configFile: Name of the main configuration JSON file
    # Default: "config.json"
    config["configFile"] = os.getenv("OFSC_CONFIG_FILE_NAME", "config.json")

    # authFile: Name of the authentication JSON file
    # Default: "auth.json"
    config["authFile"] = os.getenv("OFSC_AUTH_FILE_NAME", "auth.json")

    # databaseFile: Name of the SQLite database file
    # Default: "models.db"
    config["databaseFile"] = os.getenv("OFSC_DATABASE_FILE_NAME", "models.db")

    # mainProfile: Name of the main profile directory/file
    # Default: "main_profile"
    config["mainProfile"] = os.getenv("OFSC_MAIN_PROFILE_NAME", "main_profile")

    # requestAuth: Name of the request authentication JSON file
    # Default: "request_auth.json"
    config["requestAuth"] = os.getenv(
        "OFSC_REQUEST_AUTH_FILE_NAME", "request_auth.json"
    )

    return config
