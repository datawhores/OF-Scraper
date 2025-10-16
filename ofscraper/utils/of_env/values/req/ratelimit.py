import os


def load_ratelimit_config():
    """
    Loads comprehensive rate-limit configurations from environment variables
    with sensible default values. This is the single source of truth for all
    backoff and sleeper-related settings.

    Returns:
        A dictionary containing all loaded rate-limit configuration settings.
    """
    config = {}

    # --- Dynamic Session Sleep Configuration (For Standard API: 429/504 Rate Limiting) ---
    config["SESSION_SLEEP_INIT"] = float(os.getenv("OFSC_SESSION_SLEEP_INIT", "2.5"))
    config["SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["SESSION_SLEEP_MAX"] = float(os.getenv("OFSC_SESSION_SLEEP_MAX", "180"))
    config["SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["SESSION_MIN_SLEEP"] = float(os.getenv("OFSC_SESSION_MIN_SLEEP", "2"))

    # --- Dynamic Session Sleep Configuration (For Standard API: 403 Forbidden Errors) ---
    config["SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_INIT", "8")
    )
    config["SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "60")
    )
    config["SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_MAX", "180")
    )
    config["SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_SESSION_403_MIN_SLEEP", "0")
    )

    # --- Dynamic Session Sleep Configuration (For Downloads: 429/504 Rate Limiting) ---
    config["DOWNLOAD_SESSION_SLEEP_INIT"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_INIT", "0")
    )
    config["DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["DOWNLOAD_SESSION_SLEEP_MAX"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_MAX", "180")
    )
    config["DOWNLOAD_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["DOWNLOAD_SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["DOWNLOAD_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["DOWNLOAD_SESSION_MIN_SLEEP"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_MIN_SLEEP", "0")
    )

    # --- Dynamic Session Sleep Configuration (For Downloads: 403 Forbidden Errors) ---
    config["DOWNLOAD_SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_INIT", "4")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "80")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_MAX", "180")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD", "70")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["DOWNLOAD_SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_MIN_SLEEP", "0")
    )

    # --- Dynamic Session Sleep Configuration (For CDM: 429/504 Rate Limiting) ---
    config["CDM_SESSION_SLEEP_INIT"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_INIT", "0")
    )
    config["CDM_SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["CDM_SESSION_SLEEP_MAX"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_MAX", "180")
    )
    config["CDM_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["CDM_SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["CDM_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["CDM_SESSION_MIN_SLEEP"] = float(
        os.getenv("OFSC_CDM_SESSION_MIN_SLEEP", "4")
    )

    # --- Dynamic Session Sleep Configuration (For CDM: 403 Forbidden Errors) ---
    config["CDM_SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_INIT", "8")
    )
    config["CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "60")
    )
    config["CDM_SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_MAX", "180")
    )
    config["CDM_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["CDM_SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["CDM_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["CDM_SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_CDM_SESSION_403_MIN_SLEEP", "0")
    )

    # --- Dynamic Session Sleep Configuration (For Like Operations: 429/504 Rate Limiting) ---
    config["LIKE_SESSION_SLEEP_INIT"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_INIT", "8")
    )
    config["LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF", "4")
    )
    config["LIKE_SESSION_SLEEP_MAX"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_MAX", "120")
    )
    config["LIKE_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["LIKE_SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["LIKE_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["LIKE_SESSION_MIN_SLEEP"] = float(
        os.getenv("OFSC_LIKE_SESSION_MIN_SLEEP", "0")
    )

    # --- Dynamic Session Sleep Configuration (For Like Operations: 403 Forbidden Errors) ---
    config["LIKE_SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_INIT", "8")
    )
    config["LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "4")
    )
    config["LIKE_SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_MAX", "120")
    )
    config["LIKE_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["LIKE_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["LIKE_SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_MIN_SLEEP", "0")
    )

    # --- Dynamic Session Sleep Configuration (For Metadata: 429/504 Rate Limiting) ---
    config["METADATA_SESSION_SLEEP_INIT"] = float(
        os.getenv("OFSC_METADATA_SESSION_SLEEP_INIT", "4")
    )
    config["METADATA_SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_METADATA_SESSION_SLEEP_INCREASE_TIME_DIFF", "35")
    )
    config["METADATA_SESSION_SLEEP_MAX"] = float(
        os.getenv("OFSC_METADATA_SESSION_SLEEP_MAX", "60")
    )
    config["METADATA_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_METADATA_SESSION_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["METADATA_SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_METADATA_SESSION_SLEEP_DECAY_THRESHOLD", "35")
    )
    config["METADATA_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_METADATA_SESSION_SLEEP_DECAY_FACTOR", "2")
    )
    config["METADATA_SESSION_MIN_SLEEP"] = float(
        os.getenv("OFSC_METADATA_SESSION_MIN_SLEEP", "2")
    )

    # --- Dynamic Session Sleep Configuration (For Metadata: 403 Forbidden Errors) ---
    config["METADATA_SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_SLEEP_INIT", "4")
    )
    config["METADATA_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "35")
    )
    config["METADATA_SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_SLEEP_MAX", "60")
    )
    config["METADATA_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["METADATA_SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_SLEEP_DECAY_THRESHOLD", "30")
    )
    config["METADATA_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_SLEEP_DECAY_FACTOR", "2")
    )
    config["METADATA_SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_METADATA_SESSION_403_MIN_SLEEP", "2")
    )

    # --- Dynamic Session Sleep Configuration (For Discord: 429/504 Rate Limiting) ---
    config["DISCORD_SESSION_SLEEP_INIT"] = float(
        os.getenv("OFSC_DISCORD_SESSION_SLEEP_INIT", "5")
    )
    config["DISCORD_SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_DISCORD_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["DISCORD_SESSION_SLEEP_MAX"] = float(
        os.getenv("OFSC_DISCORD_SESSION_SLEEP_MAX", "60")
    )
    config["DISCORD_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_DISCORD_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["DISCORD_SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_DISCORD_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["DISCORD_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_DISCORD_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["DISCORD_SESSION_MIN_SLEEP"] = float(
        os.getenv("OFSC_DISCORD_SESSION_MIN_SLEEP", "2")
    )

    # --- Dynamic Session Sleep Configuration (For Discord: 403 Forbidden Errors) ---
    config["DISCORD_SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_SLEEP_INIT", "4")
    )
    config["DISCORD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["DISCORD_SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_SLEEP_MAX", "300")
    )
    config["DISCORD_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_SLEEP_INCREASE_FACTOR", "4")
    )
    config["DISCORD_SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_SLEEP_DECAY_THRESHOLD", "60")
    )
    config["DISCORD_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["DISCORD_SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_DISCORD_SESSION_403_MIN_SLEEP", "30")
    )

    # --- Dynamic Session Sleep Configuration (For Subscription API: 429/504 Rate Limiting) ---
    config["SUBSCRIPTION_SESSION_SLEEP_INIT"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_SLEEP_INIT", "1")
    )
    config["SUBSCRIPTION_SESSION_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["SUBSCRIPTION_SESSION_SLEEP_MAX"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_SLEEP_MAX", "180")
    )
    config["SUBSCRIPTION_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["SUBSCRIPTION_SESSION_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["SUBSCRIPTION_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["SUBSCRIPTION_SESSION_MIN_SLEEP"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_MIN_SLEEP", ".5")
    )

    # --- Dynamic Session Sleep Configuration (For Subscription API: 403 Forbidden Errors) ---
    config["SUBSCRIPTION_SESSION_403_SLEEP_INIT"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_SLEEP_INIT", "2")
    )
    config["SUBSCRIPTION_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "60")
    )
    config["SUBSCRIPTION_SESSION_403_SLEEP_MAX"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_SLEEP_MAX", "180")
    )
    config["SUBSCRIPTION_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["SUBSCRIPTION_SESSION_403_SLEEP_DECAY_THRESHOLD"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["SUBSCRIPTION_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config["SUBSCRIPTION_SESSION_403_MIN_SLEEP"] = float(
        os.getenv("OFSC_SUBSCRIPTION_SESSION_403_MIN_SLEEP", "0")
    )

    return config
