import os


def load_req_live_config():
    """
    Loads livestream polling, concurrency, and timeout settings from
    environment variables with default values.

    Returns:
        A dictionary containing all loaded livestream request settings.
    """
    config = {}

    # LIVE_CHECK_CONCURRENCY: Maximum simultaneous per-creator status checks during `--live` / `--live-watch` polling.
    # Default: 5
    config["LIVE_CHECK_CONCURRENCY"] = max(
        1, int(os.getenv("OFSC_LIVE_CHECK_CONCURRENCY", "5"))
    )

    # LIVE_CHECK_TIMEOUT: Timeout in seconds for a single livestream status check during recording.
    # Default: 15
    config["LIVE_CHECK_TIMEOUT"] = max(
        1, int(os.getenv("OFSC_LIVE_CHECK_TIMEOUT", "15"))
    )

    # LIVE_JITTER: Maximum random jitter in seconds added to the `--live-watch` polling interval.
    # Default: 10
    config["LIVE_JITTER"] = max(0, int(os.getenv("OFSC_LIVE_JITTER", "10")))

    # LIVE_MAX_FAILURES: Consecutive failed stream-recovery attempts before stopping a Fansly recording.
    # Default: 3
    config["LIVE_MAX_FAILURES"] = max(
        1, int(os.getenv("OFSC_LIVE_MAX_FAILURES", "3"))
    )

    return config
