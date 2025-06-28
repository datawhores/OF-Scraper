import os


def load_path_bytes_config():
    """
    Loads path bytes configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded path bytes configuration settings.
    """
    config = {}

    # --- Bytes for Paths Configuration ---
    # NORMAL_CHAR_SIZE_WINDOWS: Byte size for normal characters on Windows
    # Default: 2
    config["NORMAL_CHAR_SIZE_WINDOWS"] = int(os.getenv("NORMAL_CHAR_SIZE_WINDOWS", "2"))

    # SPECIAL_CHAR_SIZE_WINDOWS: Byte size for special characters on Windows
    # Default: 4
    config["SPECIAL_CHAR_SIZE_WINDOWS"] = int(
        os.getenv("SPECIAL_CHAR_SIZE_WINDOWS", "4")
    )

    # SPECIAL_CHAR_SIZE_UNIX: Byte size for special characters on Unix-like systems
    # Default: 4
    config["SPECIAL_CHAR_SIZE_UNIX"] = int(os.getenv("SPECIAL_CHAR_SIZE_UNIX", "4"))

    # NORMAL_CHAR_SIZE_UNIX: Byte size for normal characters on Unix-like systems
    # Default: 2
    config["NORMAL_CHAR_SIZE_UNIX"] = int(os.getenv("NORMAL_CHAR_SIZE_UNIX", "2"))

    # UTF: UTF encoding setting (e.g., "utf-8", "utf-16"). Defaults to None.
    # If set via environment, it will be a string; otherwise, it remains None.
    config["UTF"] = os.getenv("UTF", None)
    # No explicit type conversion needed if it's expected to be a string or None.
    # If you later expect a specific encoding object, that conversion would happen where used.

    return config
