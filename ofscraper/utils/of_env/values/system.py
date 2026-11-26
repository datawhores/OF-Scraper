import os


def load_system_config():
    """
    Loads subprocess logging configuration from environment variables with default values.

    Returns:
        A dictionary containing all loaded subprocess logging configuration settings.
    """
    config = {}

    ## --- Subprocess Log Level Configuration ---
    ## LOG LEVEL of 0 will disable that output
    # Set log level for user-defined scripts
    config["AFTER_DOWNLOAD_ACTION_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_AFTER_DOWNLOAD_ACTION_SCRIPT_SUBPROCESS_LEVEL", "10")
    )
    config["AFTER_LIKE_ACTION_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_AFTER_LIKE_ACTION_SCRIPT_SUBPROCESS_LEVEL", "10")
    )
    config["NAMING_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_NAMING_SCRIPT_SUBPROCESS_LEVEL", "10")
    )
    config["SKIP_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_SKIP_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL", "10")
    )
    config["AFTER_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_AFTER_DOWNLOAD_SCRIPT_SUBPROCESS_LEVEL", "10")
    )
    config["FINAL_SCRIPT_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_FINAL_SCRIPT_SUBPROCESS_LEVEL", "10")
    )

    # OFSC_LOG_SUBPROCESS_LEVELL is the old misspelled name, kept for compatibility
    config["LOG_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_LOG_SUBPROCESS_LEVEL")
        or os.getenv("OFSC_LOG_SUBPROCESS_LEVELL", "10")
    )

    # Set log level for FFmpeg operations
    config["FFMPEG_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_FFMPEG_SUBPROCESS_LEVEL", "10")
    )
    # Set log level for FFprobe operations
    config["FFPROBE_SUBPROCESS_LEVEL"] = int(
        os.getenv("OFSC_FFPROBE_SUBPROCESS_LEVEL", "10")
    )

    # OFSC_DATABASE_URL: A PostgreSQL connection URL, such as postgresql://user:password@host:5432/database. Empty (the default) keeps one SQLite file per creator. With a URL, every creator's rows are kept in that PostgreSQL database instead; this needs the PostgreSQL driver (psycopg), which is installed with OF-Scraper on macOS, 64-bit Windows and 64-bit Linux (x86_64, aarch64, ppc64le, riscv64) and is in the Docker image. Elsewhere, the first run with a URL offers to install it (`OFSC_INSTALL_EXTRAS`), or install the `postgres` extra.
    config["OFSC_DATABASE_URL"] = os.getenv("OFSC_DATABASE_URL", "")

    # INSTALL_EXTRAS: Whether a feature that needs an optional extra installs it the first time it's used: the `live` packages and the Chromium browser for OnlyFans livestreams, and the PostgreSQL driver when `OFSC_DATABASE_URL` is set on a system it isn't installed with by default. It asks first, and only at a terminal: the daemon, runs without a terminal (cron, services) and root under sudo are given the install command instead. They go into the Python running OF-Scraper, with pip, or with uv when that Python has no pip, using `OFSC_PROXY` when set. When False, or when the install is declined or fails, the feature stops and says how to install the extra. The standalone download never installs anything.
    # Default: True
    config["INSTALL_EXTRAS"] = os.getenv("OFSC_INSTALL_EXTRAS", "True").strip().lower() in (
        "true",
        "1",
    )

    # Free Space
    config["DISK_SPACE_CHECK_PATH"] = os.getenv("OFSC_DISK_SPACE_CHECK_PATH", "/")

    return config
