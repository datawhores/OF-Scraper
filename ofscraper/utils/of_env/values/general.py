import os
import json  # Required for parsing lists/sets from environment variables if you chose to allow it


def load_general_config():
    """
    Loads general application configuration settings from environment variables with default values.

    Returns:
        A dictionary containing all loaded general configuration settings.
    """
    config = {}

    # --- Output and Display Configuration ---
    # SUPRESS_OUTPUTS: A set of log levels or output types to suppress.
    # Default: {"CRITICAL", "ERROR", "WARNING", "OFF", "LOW", "PROMPT"}
    # Expects a comma-separated string if provided via environment variable.
    supress_outputs_env = os.getenv("OFSC_SUPRESS_OUTPUTS")
    if supress_outputs_env:
        config["SUPRESS_OUTPUTS"] = {s.strip() for s in supress_outputs_env.split(",")}
    else:
        config["SUPRESS_OUTPUTS"] = {
            "CRITICAL",
            "ERROR",
            "WARNING",
            "OFF",
            "LOW",
            "PROMPT",
        }

    # refreshScreen: Frequency to refresh the screen (e.g., for progress updates).
    # Default: 50
    config["refreshScreen"] = int(os.getenv("OFSC_REFRESH_SCREEN", "50"))

    # SHOW_AVATAR: Whether to show avatar in certain displays.
    # Default: True
    config["SHOW_AVATAR"] = os.getenv("OFSC_SHOW_AVATAR", "True").lower() in (
        "true",
        "1",
    )

    # SHOW_RESULTS_LOG: Whether to show results in the log.
    # Default: True
    config["SHOW_RESULTS_LOG"] = os.getenv("OFSC_SHOW_RESULTS_LOG", "True").lower() in (
        "true",
        "1",
    )

    # MODEL_PRICE_PLACEHOLDER: Placeholder text for unknown model prices.
    # Default: "Unknown_Price"
    config["MODEL_PRICE_PLACEHOLDER"] = os.getenv(
        "OFSC_MODEL_PRICE_PLACEHOLDER", "Unknown_Price"
    )

    # DELETED_MODEL_PLACEHOLDER: Placeholder text for deleted models.
    # Default: "modeldeleted"
    config["DELETED_MODEL_PLACEHOLDER"] = os.getenv(
        "OFSC_DELETED_MODEL_PLACEHOLDER", "modeldeleted"
    )

    # APP_TOKEN: A generic application token (example, usually sensitive and not hardcoded).
    # Default: "33d57ade8c02dbc5a333db99ff9ae26a"
    config["APP_TOKEN"] = os.getenv(
        "OFSC_APP_TOKEN", "33d57ade8c02dbc5a333db99ff9ae26a"
    )

    # CONTINUE_BOOL: General boolean flag for continuing operations.
    # Default: True
    config["CONTINUE_BOOL"] = os.getenv("OFSC_CONTINUE_BOOL", "True").lower() in (
        "true",
        "1",
    )

    # FILE_COUNT_PLACEHOLDER: Flag related to file count display or logic.
    # Default: True
    config["FILE_COUNT_PLACEHOLDER"] = os.getenv(
        "OFSC_FILE_COUNT_PLACEHOLDER", "True"
    ).lower() in ("true", "1")

    # FILTER_SELF_MEDIA: Whether to filter media belonging to self-profile.
    # Default: True
    config["FILTER_SELF_MEDIA"] = os.getenv(
        "OFSC_FILTER_SELF_MEDIA", "True"
    ).lower() in ("true", "1")

    # ALLOW_DUPE_MEDIA: Whether to allow duplicate media downloads.
    # Default: False
    config["ALLOW_DUPE_MEDIA"] = os.getenv(
        "OFSC_ALLOW_DUPE_MEDIA", "False"
    ).lower() in ("true", "1")

    # --- Data Processing and File Handling ---
    # NUMBER_REGEX: Regex pattern for numbers.
    # Default: "[0-9]"
    config["NUMBER_REGEX"] = os.getenv("OFSC_NUMBER_REGEX", "[0-9]")

    # USERNAME_REGEX: Regex pattern for usernames (excluding slash).
    # Default: "[^/]"
    config["USERNAME_REGEX"] = os.getenv("OFSC_USERNAME_REGEX", "[^/]")

    # BUF_SIZE: Buffer size for file operations (bytes).
    # Default: 1 MB (1024 * 1024)
    config["BUF_SIZE"] = int(os.getenv("OFSC_BUF_SIZE", str(1024 * 1024)))

    # LARGE_TRACE_CHUNK_SIZE: Chunk size for large tracing operations.
    # Default: 100
    config["LARGE_TRACE_CHUNK_SIZE"] = int(
        os.getenv("OFSC_LARGE_TRACE_CHUNK_SIZE", "100")
    )

    # --- Disclaimers (Long text, best as internal constant unless specific JSON override is designed) ---
    # disclaimers: List of legal disclaimers.
    # If provided via environment, expect a JSON string representing a list of strings.
    disclaimers_env = os.getenv("OFSC_DISCLAIMERS")
    if disclaimers_env:
        try:
            config["disclaimers"] = json.loads(disclaimers_env)
        except json.JSONDecodeError:
            print(
                f"Warning: OFSC_DISCLAIMERS environment variable is not valid JSON. Using default disclaimers."
            )
            config["disclaimers"] = [
                "This tool is not affiliated, associated, or partnered with OnlyFans in any way. We are not authorized, endorsed, or sponsored by OnlyFans. All OnlyFans trademarks remain the property of Fenix International Limited.",
                "This tool is for educational purposes only and is not intended for actual use. Should you choose to actually use it you accept all consequences and agree that you are not using it to redistribute content or for any other action that will cause loss of revenue to creators or platforms scraped.",
            ]
    else:
        config["disclaimers"] = [
            "This tool is not affiliated, associated, or partnered with OnlyFans in any way. We are not authorized, endorsed, or sponsored by OnlyFans. All OnlyFans trademarks remain the property of Fenix International Limited.",
            "This tool is for educational purposes only and is not intended for actual use. Should you choose to actually use it you accept all consequences and agree that you are not using it to redistribute content or for any other action that will cause loss of revenue to creators or platforms scraped.",
        ]

    return config
