import os


def load_metadata_config():
    """
    Loads metadata-related configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded metadata configuration settings.
    """
    config = {}

    # --- Metadata Configuration ---
    # REMOVE_UNVIEWABLE_METADATA: Defined but not read anywhere.
    # Default: False
    # Environment variable will be parsed: "True", "true", "1" -> True; "False", "false", "0" -> False
    remove_unviewable_metadata_env = os.getenv("REMOVE_UNVIEWABLE_METADATA", "False")
    config["REMOVE_UNVIEWABLE_METADATA"] = remove_unviewable_metadata_env.lower() in (
        "true",
        "1",
    )

    # QUALITY_UNKNOWN_DEFAULT: Fallback value for the `{quality}` placeholder when a media item's quality isn't known (such as non-videos or text files).
    # Default: "source"
    config["QUALITY_UNKNOWN_DEFAULT"] = os.getenv("QUALITY_UNKNOWN_DEFAULT", "source")
    config["ALT_FORCE_KEY"] = os.getenv("OFSC_ALT_FORCE_KEY", "True").lower() in (
        "true",
        "1",
    )

    return config
