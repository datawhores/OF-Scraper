import os


def load_general_paths_config():
    """
    Loads general paths configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded general paths configuration settings.
    """
    config = {}

    # --- General Paths Configuration ---
    # BATCH_TEMPFILE_CLEANUP: Flag to enable or disable cleanup of temporary files in batches.
    # Default: False
    config["BATCH_TEMPFILE_CLEANUP"] = os.getenv(
        "OFSC_BATCH_TEMPFILE_CLEANUP", "False"
    ).lower() in ("true", "1")

    return config
