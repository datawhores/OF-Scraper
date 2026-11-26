import os


def load_path_bytes_config():
    """
    Loads path bytes configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded path bytes configuration settings.
    """
    config = {}

    # --- Bytes for Paths Configuration ---
    # NORMAL_CHAR_SIZE_WINDOWS: Defined but not read anywhere. Windows path length is counted in UTF-16 units, 2 bytes each.
    # Default: 2
    config["NORMAL_CHAR_SIZE_WINDOWS"] = int(os.getenv("NORMAL_CHAR_SIZE_WINDOWS", "2"))

    # SPECIAL_CHAR_SIZE_WINDOWS: Defined but not read anywhere. Windows path length is counted in UTF-16 units, 2 bytes each.
    # Default: 4
    config["SPECIAL_CHAR_SIZE_WINDOWS"] = int(
        os.getenv("SPECIAL_CHAR_SIZE_WINDOWS", "4")
    )

    # SPECIAL_CHAR_SIZE_UNIX: Estimated byte size per non-ASCII character when measuring path length on Unix-like systems (used when `UTF` is unset).
    # Default: 4
    config["SPECIAL_CHAR_SIZE_UNIX"] = int(os.getenv("SPECIAL_CHAR_SIZE_UNIX", "4"))

    # NORMAL_CHAR_SIZE_UNIX: Estimated byte size per ASCII character when measuring path length on Unix-like systems (used when `UTF` is unset).
    # Default: 2
    config["NORMAL_CHAR_SIZE_UNIX"] = int(os.getenv("NORMAL_CHAR_SIZE_UNIX", "2"))

    # UTF: Encoding name (for example `utf-8`) used to measure exact path byte length on Linux, instead of the `*_CHAR_SIZE_UNIX` estimates. Not used on Windows, where path length is always counted in UTF-16 units.
    #
    # If set via environment, it will be a string; otherwise, it remains None.
    config["UTF"] = os.getenv("UTF", None)
    # No explicit type conversion needed if it's expected to be a string or None.
    # If you later expect a specific encoding object, that conversion would happen where used.

    return config
