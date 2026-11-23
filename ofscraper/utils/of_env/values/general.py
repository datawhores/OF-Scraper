import os


def load_general_config():
    """
    Loads general application configuration settings from environment variables with default values.

    Returns:
        A dictionary containing all loaded general configuration settings.
    """
    config = {}

    # --- Output and Display Configuration ---
    # SUPRESS_OUTPUTS: Output levels (`--output`) at which `lowstdout()` silences standard output.
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

    # refreshScreen: Defined but not read anywhere.
    # Default: 50
    config["refreshScreen"] = int(os.getenv("OFSC_REFRESH_SCREEN", "50"))

    # SHOW_AVATAR: Whether to include the creator's avatar URL in scrape headers and summaries.
    # Default: True
    config["SHOW_AVATAR"] = os.getenv("OFSC_SHOW_AVATAR", "True").lower() in (
        "true",
        "1",
    )

    # SHOW_RESULTS_LOG: Whether to print the final run summary log at exit.
    # Default: True
    config["SHOW_RESULTS_LOG"] = os.getenv("OFSC_SHOW_RESULTS_LOG", "True").lower() in (
        "true",
        "1",
    )

    # MODEL_PRICE_PLACEHOLDER: Fallback value for price placeholders (`{current_price}`, `{regular_price}`, `{promo_price}`, `{renewal_price}`) when a creator's model isn't loaded.
    # Default: "Unknown_Price"
    config["MODEL_PRICE_PLACEHOLDER"] = os.getenv(
        "OFSC_MODEL_PRICE_PLACEHOLDER", "Unknown_Price"
    )

    # DELETED_MODEL_PLACEHOLDER: Fallback username prefix used for deleted accounts whose real username isn't recorded.
    # Default: "modeldeleted"
    config["DELETED_MODEL_PLACEHOLDER"] = os.getenv(
        "OFSC_DELETED_MODEL_PLACEHOLDER", "modeldeleted"
    )

    # APP_TOKEN: The OnlyFans `app-token` header value sent on API requests.
    # Default: "33d57ade8c02dbc5a333db99ff9ae26a"
    config["APP_TOKEN"] = os.getenv(
        "OFSC_APP_TOKEN", "33d57ade8c02dbc5a333db99ff9ae26a"
    )

    # CONTINUE_BOOL: When off, skips the interactive "Do you want to continue with script" prompt and carries on as if you answered Yes.
    # Default: True
    config["CONTINUE_BOOL"] = os.getenv("OFSC_CONTINUE_BOOL", "True").lower() in (
        "true",
        "1",
    )

    # FILE_COUNT_PLACEHOLDER: When on, appends `_<count>` to multi-media filenames when `file_format` doesn't include a unique filename or media ID placeholder.
    # Default: True
    config["FILE_COUNT_PLACEHOLDER"] = os.getenv(
        "OFSC_FILE_COUNT_PLACEHOLDER", "True"
    ).lower() in ("true", "1")

    # FILTER_SELF_MEDIA: Whether to skip the account's own media: the media in messages you sent, and your own profile's media when you scrape it. Set it to False to download them.
    # Default: True
    config["FILTER_SELF_MEDIA"] = os.getenv(
        "OFSC_FILTER_SELF_MEDIA", "True"
    ).lower() in ("true", "1")

    # ALLOW_DUPE_MEDIA: The default for --allow-dupes: download media that is in several posts once for each post. The option overrides it for one run.
    # Default: False
    config["ALLOW_DUPE_MEDIA"] = os.getenv(
        "OFSC_ALLOW_DUPE_MEDIA", "False"
    ).lower() in ("true", "1")

    # --- Data Processing and File Handling ---
    # NUMBER_REGEX: Single-character regex class used to match numeric IDs in URLs for `manual` and `*_check` commands.
    # Default: "[0-9]"
    config["NUMBER_REGEX"] = os.getenv("OFSC_NUMBER_REGEX", "[0-9]")

    # USERNAME_REGEX: Single-character regex class used to match usernames in URLs for `manual` and `*_check` commands.
    # Default: "[^/]"
    config["USERNAME_REGEX"] = os.getenv("OFSC_USERNAME_REGEX", "[^/]")

    # BUF_SIZE: Read buffer size, in bytes, used when hashing files (including the duplicate check before a download is moved into place).
    # Default: 1 MB (1024 * 1024)
    config["BUF_SIZE"] = int(os.getenv("OFSC_BUF_SIZE", str(1024 * 1024)))

    # LARGE_TRACE_CHUNK_SIZE: Defined but not read anywhere.
    # Default: 100
    config["LARGE_TRACE_CHUNK_SIZE"] = int(
        os.getenv("OFSC_LARGE_TRACE_CHUNK_SIZE", "100")
    )



    # SKIP_UNAVAILABLE_DEFAULT: Default for `advanced_options.skip_unavailable_content`.
    config["SKIP_UNAVAILABLE_DEFAULT"] = os.getenv(
        "OFSC_SKIP_UNAVAILABLE_DEFAULT", "True"
    ).lower() in ("true", "1")

    # EXPIRED_GRACE_DEFAULT: Grace period, in days, after a subscription's expiry during which the creator is still treated as active for filtering and scanning.
    config["EXPIRED_GRACE_DEFAULT"] = int(
        os.getenv("OFSC_EXPIRED_GRACE_DEFAULT", "1")
    )
    return config
