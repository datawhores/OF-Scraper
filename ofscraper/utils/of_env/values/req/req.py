import os


def load_network_config():
    """
    Loads comprehensive network and session-related configuration from environment variables
    with default values.

    Returns:
        A dictionary containing all loaded network configuration settings.
    """
    config = {}

    # --- Connection and Timeout Configuration ---
    # CONNECT_TIMEOUT: Default connection timeout, in seconds, for HTTP sessions that don't pass their own.
    # Default: 15
    config["CONNECT_TIMEOUT"] = int(os.getenv("OFSC_CONNECT_TIMEOUT", "15"))

    # POOL_CONNECT_TIMEOUT: Default time, in seconds, allowed to get a connection, for HTTP sessions that don't pass their own.
    # Default: 15
    config["POOL_CONNECT_TIMEOUT"] = int(os.getenv("OFSC_POOL_CONNECT_TIMEOUT", "15"))

    # OF_READ_TIMEOUT: Longest wait for the next piece of a response (seconds),
    # for requests that don't pass their own read timeout. It isn't a limit
    # on the whole response: a slow response that keeps sending is fine.
    # On a kept connection that has answered before, a GET's answer must
    # start within a third of this, or that connection is dropped and the
    # request is retried.
    # 0 means no limit (the session manager turns it into None).
    # Default: 60
    config["OF_READ_TIMEOUT"] = int(os.getenv("OFSC_READ_TIMEOUT", "60"))

    # MAX_CONNECTIONS: Default maximum simultaneous connections for HTTP sessions that don't pass their own limit.
    # Default: 200
    config["MAX_CONNECTIONS"] = int(os.getenv("OFSC_MAX_CONNECTIONS", "200"))

    # API_MAX_CONNECTION: Default maximum simultaneous connections for API sessions (OnlyFans and Fansly).
    # Default: 100
    config["API_MAX_CONNECTION"] = int(os.getenv("OFSC_API_MAX_CONNECTION", "100"))

    # TOTAL_TIMEOUT: Default total request timeout, in seconds, for HTTP sessions that don't pass their own (`None` means no limit).
    total_timeout_env = os.getenv("OFSC_TOTAL_TIMEOUT", None)
    if total_timeout_env is not None:
        try:
            config["TOTAL_TIMEOUT"] = int(total_timeout_env)
        except ValueError:
            print(
                f"Warning: OFSC_TOTAL_TIMEOUT environment variable '{total_timeout_env}' is not a valid integer. Using default None."
            )
            config["TOTAL_TIMEOUT"] = None
    else:
        config["TOTAL_TIMEOUT"] = None

    # KEEP_ALIVE: The most idle connections the sync client keeps open to use again. A count, not a time. The async client, which downloads, has no such limit.
    # Default: 20
    config["KEEP_ALIVE"] = int(os.getenv("OFSC_KEEP_ALIVE", "20"))

    # KEEP_ALIVE_EXP: How long an idle connection is kept open to use again (seconds). Applies to both clients. 0 keeps none: each connection is closed after use.
    # Default: 10
    config["KEEP_ALIVE_EXP"] = int(os.getenv("OFSC_KEEP_ALIVE_EXP", "10"))

    # --- Proxy Configuration ---
    # PROXY: Proxy URL for all HTTP sessions (`http://` or `https://` only; SOCKS isn't supported). When unset, most requests use no proxy, but some still follow `HTTP_PROXY`/`HTTPS_PROXY` from the environment.
    config["PROXY"] = os.getenv("OFSC_PROXY", None)

    # PROXY_MOUNTS: Defined but not read anywhere.
    config["PROXY_MOUNTS"] = os.getenv("OFSC_PROXY_MOUNTS", None)

    # PROXY_AUTH: Defined but not read anywhere.
    config["PROXY_AUTH"] = os.getenv("OFSC_PROXY_AUTH", None)

    # --- Chunking Configuration ---
    # MAX_CHUNK_SIZE: Defined but not read anywhere.
    # Default: 128 MB (1024 * 1024 * 128)
    config["MAX_CHUNK_SIZE"] = int(
        os.getenv("OFSC_MAX_CHUNK_SIZE", str(1024 * 1024 * 128))
    )

    # MIN_CHUNK_SIZE: Defined but not read anywhere.
    # Default: 64 KB (64 * 1024)
    config["MIN_CHUNK_SIZE"] = int(os.getenv("OFSC_MIN_CHUNK_SIZE", str(64 * 1024)))

    # CHUNK_UPDATE_COUNT: Defined but not read anywhere.
    # Default: 12
    config["CHUNK_UPDATE_COUNT"] = int(os.getenv("OFSC_CHUNK_UPDATE_COUNT", "12"))

    # CHUNK_SIZE_UPDATE_COUNT: Defined but not read anywhere.
    # Default: 15
    config["CHUNK_SIZE_UPDATE_COUNT"] = int(
        os.getenv("OFSC_CHUNK_SIZE_UPDATE_COUNT", "15")
    )

    # CHUNK_MEMORY_SPLIT: Defined but not read anywhere.
    # Default: 64
    config["CHUNK_MEMORY_SPLIT"] = int(os.getenv("OFSC_CHUNK_MEMORY_SPLIT", "64"))

    # CHUNK_FILE_SPLIT: Defined but not read anywhere.
    # Default: 64
    config["CHUNK_FILE_SPLIT"] = int(os.getenv("OFSC_CHUNK_FILE_SPLIT", "64"))

    # MAX_READ_SIZE: Defined but not read anywhere.
    # Default: 16 MB (1024 * 1024 * 16)
    config["MAX_READ_SIZE"] = int(
        os.getenv("OFSC_MAX_READ_SIZE", str(1024 * 1024 * 16))
    )

    # CHUNK_TIMEOUT_SEC: Read timeout, in seconds, for download and Fansly stream requests (overrides `OF_READ_TIMEOUT` for downloads).
    # Default: 30
    config["CHUNK_TIMEOUT_SEC"] = int(os.getenv("OFSC_CHUNK_TIMEOUT_SEC", "30"))

    # --- Semaphore and Concurrency Configuration ---
    # REQ_SEMAPHORE_MULTI: Defined but not read anywhere.
    # Default: 5
    config["REQ_SEMAPHORE_MULTI"] = int(os.getenv("OFSC_REQ_SEMAPHORE_MULTI", "5"))

    # SCRAPE_PAID_SEMS: Maximum concurrent requests when scraping the paid page (`--scrape-paid`).
    # Default: 10
    config["SCRAPE_PAID_SEMS"] = int(os.getenv("OFSC_SCRAPE_PAID_SEMS", "10"))

    # SUBSCRIPTION_SEMS: Maximum concurrent requests when fetching subscription lists and profiles.
    # Default: 5
    config["SUBSCRIPTION_SEMS"] = int(os.getenv("OFSC_SUBSCRIPTION_SEMS", "5"))

    # LIKE_MAX_SEMS: Defined but not read anywhere.
    # Default: 12
    config["LIKE_MAX_SEMS"] = int(os.getenv("OFSC_LIKE_MAX_SEMS", "12"))

    # MAX_SEMS_BATCH_DOWNLOAD: Defined but not read anywhere.
    # Default: 12
    config["MAX_SEMS_BATCH_DOWNLOAD"] = int(
        os.getenv("OFSC_MAX_SEMS_BATCH_DOWNLOAD", "12")
    )

    # MAX_SEMS_SINGLE_THREAD_DOWNLOAD: Defined but not read anywhere.
    # Default: 50
    config["MAX_SEMS_SINGLE_THREAD_DOWNLOAD"] = int(
        os.getenv("OFSC_MAX_SEMS_SINGLE_THREAD_DOWNLOAD", "50")
    )

    # SESSION_MANAGER_SYNC_SEM_DEFAULT: Default maximum concurrent synchronous requests per `sessionManager`.
    # Default: 3
    config["SESSION_MANAGER_SYNC_SEM_DEFAULT"] = int(
        os.getenv("OFSC_SESSION_MANAGER_SYNC_SEM_DEFAULT", "3")
    )

    # SESSION_MANAGER_SEM_DEFAULT: Default maximum concurrent async requests per `sessionManager`.
    # Default: 10
    config["SESSION_MANAGER_SEM_DEFAULT"] = int(
        os.getenv("OFSC_SESSION_MANAGER_SEM_DEFAULT", "10")
    )

    # MAX_THREAD_WORKERS: Defined but not read anywhere.
    # Default: 20
    config["MAX_THREAD_WORKERS"] = int(os.getenv("OFSC_MAX_THREAD_WORKERS", "20"))

    # --- Retry and Wait Configuration ---
    # OF_MIN_WAIT_SESSION_DEFAULT: Default minimum wait, in seconds, between retries in `sessionManager`.
    # Default: 2
    config["OF_MIN_WAIT_SESSION_DEFAULT"] = float(
        os.getenv("OFSC_MIN_WAIT_SESSION_DEFAULT", "2")
    )

    # OF_MAX_WAIT_SESSION_DEFAULT: Default maximum wait, in seconds, between retries in `sessionManager`.
    # Default: 3
    config["OF_MAX_WAIT_SESSION_DEFAULT"] = float(
        os.getenv("OFSC_MAX_WAIT_SESSION_DEFAULT", "3")
    )

    # OF_NUM_RETRIES_SESSION_DEFAULT: Default maximum number of attempts for a request in `sessionManager`.
    # Default: 10
    config["OF_NUM_RETRIES_SESSION_DEFAULT"] = int(
        os.getenv("OFSC_NUM_RETRIES_SESSION_DEFAULT", "10")
    )

    # OF_MIN_WAIT_API: Minimum wait, in seconds, between retries for API, download, MPD and CDM key requests.
    # Default: 2
    config["OF_MIN_WAIT_API"] = float(os.getenv("OFSC_MIN_WAIT_API", "2"))

    # OF_MAX_WAIT_API: Maximum wait, in seconds, between retries for API, download, MPD and CDM key requests.
    # Default: 3
    config["OF_MAX_WAIT_API"] = float(os.getenv("OFSC_MAX_WAIT_API", "3"))

    # OF_AUTH_MIN_WAIT: Defined but not read anywhere.
    # Default: 3
    config["OF_AUTH_MIN_WAIT"] = float(os.getenv("OFSC_AUTH_MIN_WAIT", "3"))

    # OF_AUTH_MAX_WAIT: Defined but not read anywhere.
    # Default: 3
    config["OF_AUTH_MAX_WAIT"] = float(os.getenv("OFSC_AUTH_MAX_WAIT", "3"))

    # DOWNLOAD_NUM_TRIES_REQ: Maximum request-level attempts per download outside check mode.
    # Default: 5
    config["DOWNLOAD_NUM_TRIES_REQ"] = int(
        os.getenv("OFSC_DOWNLOAD_NUM_TRIES_REQ", "5")
    )

    # DOWNLOAD_NUM_TRIES_CHECK_REQ: Maximum request-level attempts per download in check mode (`*_check` commands).
    # Default: 2
    config["DOWNLOAD_NUM_TRIES_CHECK_REQ"] = int(
        os.getenv("OFSC_DOWNLOAD_NUM_TRIES_CHECK_REQ", "2")
    )

    # AUTH_NUM_TRIES: Defined but not read anywhere.
    # Default: 3
    config["AUTH_NUM_TRIES"] = int(os.getenv("OFSC_AUTH_NUM_TRIES", "3"))

    # --- Miscellaneous ---
    # MESSAGE_SLEEP_DEFAULT: Defined but not read anywhere.
    # Default: 0
    config["MESSAGE_SLEEP_DEFAULT"] = int(os.getenv("OFSC_MESSAGE_SLEEP_DEFAULT", "0"))

    return config
