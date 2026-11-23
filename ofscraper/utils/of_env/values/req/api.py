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
    # MAX_TIMELINE_INDIVIDUAL_SEARCH: Maximum number of `--post-id` IDs fetched individually for timeline posts before falling back to a full timeline scan.
    # Default: 10
    config["MAX_TIMELINE_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_TIMELINE_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_PINNED_INDIVIDUAL_SEARCH: Defined but not read anywhere.
    # Default: 10
    config["MAX_PINNED_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_PINNED_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_ARCHIVED_INDIVIDUAL_SEARCH: Maximum number of `--post-id` IDs fetched individually for archived posts before falling back to a full archived scan.
    # Default: 10
    config["MAX_ARCHIVED_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_ARCHIVED_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_MESSAGES_INDIVIDUAL_SEARCH: Maximum number of `--post-id` IDs fetched individually for messages before falling back to a full messages scan.
    # Default: 10
    config["MAX_MESSAGES_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_MESSAGES_INDIVIDUAL_SEARCH", "10")
    )

    # MAX_STREAMS_INDIVIDUAL_SEARCH: Maximum number of `--post-id` IDs fetched individually for streams before falling back to a full streams scan.
    # Default: 10
    config["MAX_STREAMS_INDIVIDUAL_SEARCH"] = int(
        os.getenv("OFSC_MAX_STREAMS_INDIVIDUAL_SEARCH", "10")
    )

    # --- API Retry Counts ---
    # API_INDVIDIUAL_NUM_TRIES: Default maximum number of attempts for an API session request (`ofsession`), unless the caller passes `retries`.
    # Default: 3
    config["API_INDVIDIUAL_NUM_TRIES"] = int(
        os.getenv("OFSC_API_INDIVIDUAL_NUM_TRIES", "3")
    )

    # RATE_LIMIT_NUM_TRIES: Number of tries for a request that keeps getting a
    # 429. The backoff wait grows between tries, so these span minutes.
    # Default: 8
    config["RATE_LIMIT_NUM_TRIES"] = int(os.getenv("OFSC_RATE_LIMIT_NUM_TRIES", "8"))

    # API_PAID_NUM_TRIES: Defined but not read anywhere.
    # Default: 8
    config["API_PAID_NUM_TRIES"] = int(os.getenv("OFSC_API_PAID_NUM_TRIES", "8"))

    # API_CHECK_NUM_TRIES: Defined but not read anywhere.
    # Default: 10
    config["API_CHECK_NUM_TRIES"] = int(os.getenv("OFSC_API_CHECK_NUM_TRIES", "10"))

    # API_NUM_TRIES: Used only as the denominator in `[attempt X/Y]` log messages (`commands/scraper/actions/utils/log.py`); doesn't control retry counts.
    # Default: 10
    config["API_NUM_TRIES"] = int(os.getenv("OFSC_API_NUM_TRIES", "10"))

    # API_LIKE_NUM_TRIES: Default maximum number of attempts on the like/unlike session (`like.py`), though individual like/unlike requests override it with `LIKE_MAX_RETRIES`.
    # Default: 5
    config["API_LIKE_NUM_TRIES"] = int(os.getenv("OFSC_API_LIKE_NUM_TRIES", "5"))

    # --- API Page Limits ---
    # API_MAX_AREAS: Maximum number of post areas scanned at the same time for one creator.
    # Default: 2
    config["API_MAX_AREAS"] = int(os.getenv("OFSC_API_MAX_AREAS", "2"))

    # REASONABLE_MAX_PAGE: Target maximum number of concurrent pagination tasks for non-message areas.
    # Default: 50
    config["REASONABLE_MAX_PAGE"] = int(os.getenv("OFSC_REASONABLE_MAX_PAGE", "50"))

    # MIN_PAGE_POST_COUNT: Minimum number of items per pagination task, to avoid spawning many workers for small accounts.
    # Default: 50
    config["MIN_PAGE_POST_COUNT"] = int(os.getenv("OFSC_MIN_PAGE_POST_COUNT", "50"))

    # REASONABLE_MAX_PAGE_MESSAGES: Target maximum number of concurrent pagination tasks for messages.
    # Default: 80
    config["REASONABLE_MAX_PAGE_MESSAGES"] = int(
        os.getenv("OFSC_REASONABLE_MAX_PAGE_MESSAGES", "80")
    )

    # --- API Request Parameters ---
    # API_TIMEOUT_PER_TASK: Total timeout, in seconds, for each API session request in main scraper and metadata runs.
    # Default: 500
    config["API_TIMEOUT_PER_TASK"] = int(os.getenv("OFSC_API_TIMEOUT_PER_TASK", "500"))

    # API_REQUEST_THREADONLY: Defined but not read anywhere.
    # Default: ["Windows", "Linux", "Darwin"] (comma-separated string in env var)
    api_request_threadonly_env = os.getenv("OFSC_API_REQUEST_THREADONLY")
    if api_request_threadonly_env:
        config["API_REQUEST_THREADONLY"] = [
            os_name.strip() for os_name in api_request_threadonly_env.split(",")
        ]
    else:
        config["API_REQUEST_THREADONLY"] = ["Windows", "Linux", "Darwin"]

    # API_REQ_SEM_MAX: Maximum concurrent API requests in main scraper and metadata runs.
    # Default: 12
    config["API_REQ_SEM_MAX"] = int(os.getenv("OFSC_API_REQ_SEM_MAX", "12"))

    # API_REQ_CHECK_MAX: Maximum concurrent API requests in check (`*_check`) and `manual` modes.
    # Default: 12
    config["API_REQ_CHECK_MAX"] = int(os.getenv("OFSC_API_REQ_CHECK_MAX", "12"))

    return config
