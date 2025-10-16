import os


def load_metadata_config():
    """
    Loads metadata-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded metadata configuration settings.
    """
    config = {}

    # --- Metadata Configuration ---
    # REMOVE_UNVIEWABLE_METADATA: Flag to determine if unviewable metadata should be removed (boolean)
    # Default: False
    # Environment variable will be parsed: "True", "true", "1" -> True; "False", "false", "0" -> False
    remove_unviewable_metadata_env = os.getenv("REMOVE_UNVIEWABLE_METADATA", "False")
    config["REMOVE_UNVIEWABLE_METADATA"] = remove_unviewable_metadata_env.lower() in (
        "true",
        "1",
    )

    # QUALITY_UNKNOWN_DEFAULT: Default quality setting for unknown metadata
    # Default: "source"
    config["QUALITY_UNKNOWN_DEFAULT"] = os.getenv("QUALITY_UNKNOWN_DEFAULT", "source")
    config["ALT_FORCE_KEY"] = os.getenv("OFSC_ALT_FORCE_KEY", "True").lower() in (
        "true",
        "1",
    )

    return config
