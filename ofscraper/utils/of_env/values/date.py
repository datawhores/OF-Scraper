import os


def load_date_config():
    """
    Loads date format configurations from environment variables with default values.

    Returns:
        A dictionary containing all loaded date format configuration settings.
    """
    config = {}

    # --- Date Format Configuration ---
    # PROMPT_DATE_FORMAT: Date format used for user prompts or display.
    # Default: "YYYY-MM-DD"
    config["PROMPT_DATE_FORMAT"] = os.getenv("OFSC_PROMPT_DATE_FORMAT", "YYYY-MM-DD")

    # API_DATE_FORMAT: Date format used for API interactions.
    # Default: "YYYY-MM-DD HH:mm:ss"
    config["API_DATE_FORMAT"] = os.getenv("OFSC_API_DATE_FORMAT", "YYYY-MM-DD HH:mm:ss")

    return config
