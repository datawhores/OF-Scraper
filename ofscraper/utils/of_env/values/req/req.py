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
    # CONNECT_TIMEOUT: Connection timeout for general network operations (seconds).
    # Default: 35
    config["CONNECT_TIMEOUT"] = int(os.getenv("OFSC_CONNECT_TIMEOUT", "35"))

    # POOL_CONNECT_TIMEOUT: Connection timeout for pooled connections (seconds).
    # Default: 60
    config["POOL_CONNECT_TIMEOUT"] = int(os.getenv("OFSC_POOL_CONNECT_TIMEOUT", "60"))

    # MAX_CONNECTIONS: Maximum number of simultaneous network connections.
    # Default: 200
    config["MAX_CONNECTIONS"] = int(os.getenv("OFSC_MAX_CONNECTIONS", "200"))

    # API_MAX_CONNECTION: Maximum number of API connections.
    # Default: 100
    config["API_MAX_CONNECTION"] = int(os.getenv("OFSC_API_MAX_CONNECTION", "100"))

    # TOTAL_TIMEOUT: Total timeout for operations (seconds). Defaults to None.
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

    # KEEP_ALIVE: Keep-alive duration for connections (seconds).
    # Default: 20
    config["KEEP_ALIVE"] = int(os.getenv("OFSC_KEEP_ALIVE", "20"))

    # KEEP_ALIVE_EXP: Keep-alive expiration duration (seconds).
    # Default: 10
    config["KEEP_ALIVE_EXP"] = int(os.getenv("OFSC_KEEP_ALIVE_EXP", "10"))

    # --- Proxy Configuration ---
    # PROXY: Proxy URL. Defaults to None.
    config["PROXY"] = os.getenv("OFSC_PROXY", None)

    # PROXY_MOUNTS: Proxy mounts configuration (string, specific format expected by application). Defaults to None.
    config["PROXY_MOUNTS"] = os.getenv("OFSC_PROXY_MOUNTS", None)

    # PROXY_AUTH: Proxy authentication credentials (string, specific format expected by application). Defaults to None.
    config["PROXY_AUTH"] = os.getenv("OFSC_PROXY_AUTH", None)

    # --- Chunking Configuration ---
    # MAX_CHUNK_SIZE: Maximum size of a download chunk (bytes).
    # Default: 128 MB (1024 * 1024 * 128)
    config["MAX_CHUNK_SIZE"] = int(
        os.getenv("OFSC_MAX_CHUNK_SIZE", str(1024 * 1024 * 128))
    )

    # MIN_CHUNK_SIZE: Minimum size of a download chunk (bytes).
    # Default: 64 KB (64 * 1024)
    config["MIN_CHUNK_SIZE"] = int(os.getenv("OFSC_MIN_CHUNK_SIZE", str(64 * 1024)))

    # CHUNK_UPDATE_COUNT: Number of chunks before updating progress.
    # Default: 12
    config["CHUNK_UPDATE_COUNT"] = int(os.getenv("OFSC_CHUNK_UPDATE_COUNT", "12"))

    # CHUNK_SIZE_UPDATE_COUNT: Number of chunks before updating chunk size dynamically.
    # Default: 15
    config["CHUNK_SIZE_UPDATE_COUNT"] = int(
        os.getenv("OFSC_CHUNK_SIZE_UPDATE_COUNT", "15")
    )

    # CHUNK_MEMORY_SPLIT: Ideal memory split for chunk processing (e.g., in MB).
    # Default: 64
    config["CHUNK_MEMORY_SPLIT"] = int(os.getenv("OFSC_CHUNK_MEMORY_SPLIT", "64"))

    # CHUNK_FILE_SPLIT: Ideal file split size for chunk processing (e.g., in MB).
    # Default: 64
    config["CHUNK_FILE_SPLIT"] = int(os.getenv("OFSC_CHUNK_FILE_SPLIT", "64"))

    # MAX_READ_SIZE: Maximum size to read at once (bytes).
    # Default: 16 MB (1024 * 1024 * 16)
    config["MAX_READ_SIZE"] = int(
        os.getenv("OFSC_MAX_READ_SIZE", str(1024 * 1024 * 16))
    )

    # CHUNK_TIMEOUT_SEC: Timeout for individual chunk downloads (seconds).
    # Default: 120
    config["CHUNK_TIMEOUT_SEC"] = int(os.getenv("OFSC_CHUNK_TIMEOUT_SEC", "120"))

    # --- Semaphore and Concurrency Configuration ---
    # REQ_SEMAPHORE_MULTI: Semaphore limit for multiple requests.
    # Default: 5
    config["REQ_SEMAPHORE_MULTI"] = int(os.getenv("OFSC_REQ_SEMAPHORE_MULTI", "5"))

    # SCRAPE_PAID_SEMS: Semaphore limit for scraping paid content.
    # Default: 10
    config["SCRAPE_PAID_SEMS"] = int(os.getenv("OFSC_SCRAPE_PAID_SEMS", "10"))

    # SUBSCRIPTION_SEMS: Semaphore limit for subscription-related operations.
    # Default: 5
    config["SUBSCRIPTION_SEMS"] = int(os.getenv("OFSC_SUBSCRIPTION_SEMS", "5"))

    # LIKE_MAX_SEMS: Maximum semaphores for like operations.
    # Default: 12
    config["LIKE_MAX_SEMS"] = int(os.getenv("OFSC_LIKE_MAX_SEMS", "12"))

    # MAX_SEMS_BATCH_DOWNLOAD: Maximum semaphores for batch downloads.
    # Default: 12
    config["MAX_SEMS_BATCH_DOWNLOAD"] = int(
        os.getenv("OFSC_MAX_SEMS_BATCH_DOWNLOAD", "12")
    )

    # MAX_SEMS_SINGLE_THREAD_DOWNLOAD: Maximum semaphores for single-thread downloads.
    # Default: 50
    config["MAX_SEMS_SINGLE_THREAD_DOWNLOAD"] = int(
        os.getenv("OFSC_MAX_SEMS_SINGLE_THREAD_DOWNLOAD", "50")
    )

    # SESSION_MANAGER_SYNC_SEM_DEFAULT: Default semaphore for session manager sync operations.
    # Default: 3
    config["SESSION_MANAGER_SYNC_SEM_DEFAULT"] = int(
        os.getenv("OFSC_SESSION_MANAGER_SYNC_SEM_DEFAULT", "3")
    )

    # SESSION_MANAGER_SEM_DEFAULT: Default semaphore for general session manager operations.
    # Default: 10
    config["SESSION_MANAGER_SEM_DEFAULT"] = int(
        os.getenv("OFSC_SESSION_MANAGER_SEM_DEFAULT", "10")
    )

    # MAX_THREAD_WORKERS: Maximum number of threads for worker pools.
    # Default: 20
    config["MAX_THREAD_WORKERS"] = int(os.getenv("OFSC_MAX_THREAD_WORKERS", "20"))

    # --- Retry and Wait Configuration ---
    # OF_MIN_WAIT_SESSION_DEFAULT: Minimum wait time for session operations (seconds).
    # Default: 2
    config["OF_MIN_WAIT_SESSION_DEFAULT"] = float(
        os.getenv("OFSC_MIN_WAIT_SESSION_DEFAULT", "2")
    )

    # OF_MAX_WAIT_SESSION_DEFAULT: Maximum wait time for session operations (seconds).
    # Default: 6
    config["OF_MAX_WAIT_SESSION_DEFAULT"] = float(
        os.getenv("OFSC_MAX_WAIT_SESSION_DEFAULT", "6")
    )

    # OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT: Minimum wait for exponential backoff in sessions (seconds).
    # Default: 16
    config["OF_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT"] = float(
        os.getenv("OFSC_MIN_WAIT_EXPONENTIAL_SESSION_DEFAULT", "16")
    )

    # OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT: Maximum wait for exponential backoff in sessions (seconds).
    # Default: 128
    config["OF_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT"] = float(
        os.getenv("OFSC_MAX_WAIT_EXPONENTIAL_SESSION_DEFAULT", "128")
    )

    # OF_NUM_RETRIES_SESSION_DEFAULT: Number of retries for session operations.
    # Default: 10
    config["OF_NUM_RETRIES_SESSION_DEFAULT"] = int(
        os.getenv("OFSC_NUM_RETRIES_SESSION_DEFAULT", "10")
    )

    # OF_MIN_WAIT_API: Minimum wait time for API calls (seconds).
    # Default: 2
    config["OF_MIN_WAIT_API"] = float(os.getenv("OFSC_MIN_WAIT_API", "2"))

    # OF_MAX_WAIT_API: Maximum wait time for API calls (seconds).
    # Default: 6
    config["OF_MAX_WAIT_API"] = float(os.getenv("OFSC_MAX_WAIT_API", "6"))

    # OF_AUTH_MIN_WAIT: Minimum wait time for authentication operations (seconds).
    # Default: 3
    config["OF_AUTH_MIN_WAIT"] = float(os.getenv("OFSC_AUTH_MIN_WAIT", "3"))

    # OF_AUTH_MAX_WAIT: Maximum wait time for authentication operations (seconds).
    # Default: 10
    config["OF_AUTH_MAX_WAIT"] = float(os.getenv("OFSC_AUTH_MAX_WAIT", "10"))

    # DOWNLOAD_NUM_TRIES_REQ: Number of download retries for requests.
    # Default: 5
    config["DOWNLOAD_NUM_TRIES_REQ"] = int(
        os.getenv("OFSC_DOWNLOAD_NUM_TRIES_REQ", "5")
    )

    # DOWNLOAD_NUM_TRIES_CHECK_REQ: Number of download check retries for requests.
    # Default: 2
    config["DOWNLOAD_NUM_TRIES_CHECK_REQ"] = int(
        os.getenv("OFSC_DOWNLOAD_NUM_TRIES_CHECK_REQ", "2")
    )

    # AUTH_NUM_TRIES: Number of retries for authentication attempts.
    # Default: 3
    config["AUTH_NUM_TRIES"] = int(os.getenv("OFSC_AUTH_NUM_TRIES", "3"))

    # --- Miscellaneous ---
    # MESSAGE_SLEEP_DEFAULT: Default sleep duration for messages (seconds).
    # Default: 0
    config["MESSAGE_SLEEP_DEFAULT"] = int(os.getenv("OFSC_MESSAGE_SLEEP_DEFAULT", "0"))

    return config
