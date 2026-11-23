import os


def load_max_lengths_config():
    """
    Loads maximum length and size configurations from environment variables with default values.

    Returns:
        A dictionary containing all loaded maximum length/size configuration settings.
    """
    config = {}

    # --- Maximum Length/Size Configuration ---
    # MAX_TEXT_LENGTH: Wrap width, in characters, when writing downloaded post text files.
    # Default: 70
    config["MAX_TEXT_LENGTH"] = int(os.getenv("OFSC_MAX_TEXT_LENGTH", "70"))

    # MAX_TEXT_WORKER: Defined but not read anywhere.
    # Default: 30
    config["MAX_TEXT_WORKER"] = int(os.getenv("OFSC_MAX_TEXT_WORKER", "30"))

    # WINDOWS_MAX_PATH_BYTES: Maximum full path length, in bytes, before truncation on Windows.
    # Default: 530
    config["WINDOWS_MAX_PATH_BYTES"] = int(
        os.getenv("OFSC_WINDOWS_MAX_PATH_BYTES", "530")
    )

    # MAC_MAX_PATH: Maximum full path length, in characters, before truncation on macOS.
    # Default: 255
    config["MAC_MAX_PATH"] = int(os.getenv("OFSC_MAC_MAX_PATH", "255"))

    # LINUX_MAX_FILE_NAME_BYTES: Maximum filename length, in bytes, before truncation on Linux.
    # Default: 254
    config["LINUX_MAX_FILE_NAME_BYTES"] = int(
        os.getenv("OFSC_LINUX_MAX_FILE_NAME_BYTES", "254")
    )

    return config
