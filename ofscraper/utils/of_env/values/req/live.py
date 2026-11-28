import math
import os


def _positive_int(raw: str | None, default: int, minimum: int = 1) -> int:
    if raw is None:
        return default
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return default
    return max(minimum, val)


def _non_negative_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(val):
        return default
    return max(0.0, val)


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
    config["LIVE_CHECK_CONCURRENCY"] = _positive_int(
        os.getenv("OFSC_LIVE_CHECK_CONCURRENCY"), 5
    )

    # LIVE_CHECK_TIMEOUT: Timeout in seconds for a single livestream status check during recording.
    # Default: 15
    config["LIVE_CHECK_TIMEOUT"] = _positive_int(
        os.getenv("OFSC_LIVE_CHECK_TIMEOUT"), 15
    )

    # LIVE_INDIVIDUAL_MAX: Most OnlyFans creators chosen with `-u` that each `--live` / `--live-watch` check asks one by one; with more, a check reads the subscription list instead and asks this many of the chosen creators missing from it, taking turns.
    # Default: 10
    config["LIVE_INDIVIDUAL_MAX"] = _positive_int(
        os.getenv("OFSC_LIVE_INDIVIDUAL_MAX"), 10, minimum=0
    )

    # LIVE_JITTER: Maximum random jitter in seconds added to the `--live-watch` polling interval. The `--live-jitter` option overrides it for one run.
    # Default: 10.0
    config["LIVE_JITTER"] = _non_negative_float(os.getenv("OFSC_LIVE_JITTER"), 10.0)

    # LIVE_MAX_FAILURES: Consecutive failed stream-recovery attempts before stopping a Fansly recording.
    # Default: 3
    config["LIVE_MAX_FAILURES"] = _positive_int(
        os.getenv("OFSC_LIVE_MAX_FAILURES"), 3
    )

    return config
