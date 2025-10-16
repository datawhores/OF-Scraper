import os


def load_api_limits_config():
    """
    Loads API search limits, retry, and request-related configuration from
    environment variables with default values.

    Returns:
        A dictionary containing all loaded API configuration settings.
    """
    config = {}

    # --- API Search Limits ---
    # MAX_TIMELINE_INDIVIDUAL_SEARCH: Max number of timeline posts to search individually.
    # Default: 10
    config["MAX_TIMELINE_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_TIMELINE_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_PINNED_INDIVIDUAL_SEARCH: Max number of pinned posts to search individually.
    # Default: 10
    config["MAX_PINNED_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_PINNED_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_ARCHIVED_INDIVIDUAL_SEARCH: Max number of archived posts to search individually.
    # Default: 10
    config["MAX_ARCHIVED_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_ARCHIVED_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_MESSAGES_INDIVIDUAL_SEARCH: Max number of messages to search individually.
    # Default: 10
    config["MAX_MESSAGES_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_MESSAGES_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_STREAMS_INDIVIDUAL_SEARCH: Max number of streams to search individually.
    # Default: 10
    config["MAX_STREAMS_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_STREAMS_INDIVIDUAL_SEARCH", "10")
    )

    # --- API Retry Counts ---
    # API_INDVIDIUAL_NUM_TRIES: Number of tries for individual API calls.
    # Default: 3
    config["API_INDVIDIUAL_NUM_TRIES"] = int(
        os.getenv("OFSC_API_INDIVIDUAL_NUM_TRIES", "3")
    )

    # API_PAID_NUM_TRIES: Number of tries for paid content API calls.
    # Default: 8
    config["API_PAID_NUM_TRIES"] = int(os.getenv("OFSC_API_PAID_NUM_TRIES", "8"))

    # API_CHECK_NUM_TRIES: Number of tries for API checks.
    # Default: 10
    config["API_CHECK_NUM_TRIES"] = int(os.getenv("OFSC_API_CHECK_NUM_TRIES", "10"))

    # API_NUM_TRIES: General number of tries for API calls (for messages, etc.).
    # Default: 10
    config["API_NUM_TRIES"] = int(os.getenv("OFSC_API_NUM_TRIES", "10"))

    # API_LIKE_NUM_TRIES: Number of tries for API like operations.
    # Default: 5
    config["API_LIKE_NUM_TRIES"] = int(os.getenv("OFSC_API_LIKE_NUM_TRIES", "5"))

    # --- API Page Limits ---
    # API_MAX_AREAS: Max number of API areas.
    # Default: 2
    config["API_MAX_AREAS"] = int(os.getenv("OFSC_API_MAX_AREAS", "2"))

    # REASONABLE_MAX_PAGE: Reasonable max number of pages (e.g., 50 posts per page).
    # Default: 50
    config["REASONABLE_MAX_PAGE"] = int(os.getenv("OFSC_REASONABLE_MAX_PAGE", "50"))

    # MIN_PAGE_POST_COUNT: Minimum number of posts expected per page.
    # Default: 50
    config["MIN_PAGE_POST_COUNT"] = int(os.getenv("OFSC_MIN_PAGE_POST_COUNT", "50"))

    # REASONABLE_MAX_PAGE_MESSAGES: Reasonable max number of pages for messages.
    # Default: 80
    config["REASONABLE_MAX_PAGE_MESSAGES"] = int(
        os.getenv("OFSC_REASONABLE_MAX_PAGE_MESSAGES", "80")
    )

    # --- API Request Parameters ---
    # API_TIMEOUT_PER_TASK: Timeout per API task in milliseconds.
    # Default: 500
    config["API_TIMEOUT_PER_TASK"] = int(os.getenv("OFSC_API_TIMEOUT_PER_TASK", "500"))

    # API_REQUEST_THREADONLY: List of OS names where API requests should be thread-only.
    # Default: ["Windows", "Linux", "Darwin"] (comma-separated string in env var)
    api_request_threadonly_env = os.getenv("OFSC_API_REQUEST_THREADONLY")
    if api_request_threadonly_env:
        config["API_REQUEST_THREADONLY"] = [
            os_name.strip() for os_name in api_request_threadonly_env.split(",")
        ]
    else:
        config["API_REQUEST_THREADONLY"] = ["Windows", "Linux", "Darwin"]

    # API_REQ_SEM_MAX: Maximum semaphore for API requests.
    # Default: 12
    config["API_REQ_SEM_MAX"] = int(os.getenv("OFSC_API_REQ_SEM_MAX", "12"))

    # API_REQ_CHECK_MAX: Maximum checks for API requests.
    # Default: 12
    config["API_REQ_CHECK_MAX"] = int(os.getenv("OFSC_API_REQ_CHECK_MAX", "12"))

    return config
