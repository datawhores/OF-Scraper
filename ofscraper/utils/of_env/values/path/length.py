import os


def load_max_lengths_config():
    """
    Loads maximum length and size configurations from environment variables with default values.

    Returns:
        A dictionary containing all loaded maximum length/size configuration settings.
    """
    config = {}

    # --- Maximum Length/Size Configuration ---
    # MAX_TEXT_LENGTH: Maximum allowed length for certain text fields.
    # Default: 70
    config["MAX_TEXT_LENGTH"] = int(os.getenv("OFSC_MAX_TEXT_LENGTH", "70"))

    # MAX_TEXT_WORKER: Maximum number of workers for text processing.
    # Default: 30
    config["MAX_TEXT_WORKER"] = int(os.getenv("OFSC_MAX_TEXT_WORKER", "30"))

    # WINDOWS_MAX_PATH_BYTES: Maximum path length in bytes for Windows.
    # Default: 530
    config["WINDOWS_MAX_PATH_BYTES"] = int(
        os.getenv("OFSC_WINDOWS_MAX_PATH_BYTES", "530")
    )

    # MAC_MAX_PATH: Maximum path length for macOS (characters).
    # Default: 255
    config["MAC_MAX_PATH"] = int(os.getenv("OFSC_MAC_MAX_PATH", "255"))

    # LINUX_MAX_FILE_NAME_BYTES: Maximum file name length in bytes for Linux.
    # Default: 254
    config["LINUX_MAX_FILE_NAME_BYTES"] = int(
        os.getenv("OFSC_LINUX_MAX_FILE_NAME_BYTES", "254")
    )

    return config
