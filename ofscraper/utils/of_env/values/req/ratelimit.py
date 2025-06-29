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
    config["SESSION_SLEEP_INIT"] = int(os.getenv("OFSC_SESSION_SLEEP_INIT", "8"))
    config["SESSION_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["SESSION_SLEEP_MAX"] = int(os.getenv("OFSC_SESSION_SLEEP_MAX", "180"))
    config["SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["SESSION_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['SESSION_MIN_SLEEP'] = int(os.getenv('OFSC_SESSION_MIN_SLEEP', '4'))


    # --- Dynamic Session Sleep Configuration (For Standard API: 403 Forbidden Errors) ---
    config["SESSION_403_SLEEP_INIT"] = int(
        os.getenv("OFSC_SESSION_403_SLEEP_INIT", "8")
    )
    config["SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "60")
    )
    config["SESSION_403_SLEEP_MAX"] = int(
        os.getenv("OFSC_SESSION_403_SLEEP_MAX", "180")
    )
    config["SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["SESSION_403_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['SESSION_403_MIN_SLEEP'] = int(os.getenv('OFSC_SESSION_403_MIN_SLEEP', '0'))


    # --- Dynamic Session Sleep Configuration (For Downloads: 429/504 Rate Limiting) ---
    config["DOWNLOAD_SESSION_SLEEP_INIT"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_INIT", "0")
    )
    config["DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["DOWNLOAD_SESSION_SLEEP_MAX"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_MAX", "180")
    )
    config["DOWNLOAD_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["DOWNLOAD_SESSION_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["DOWNLOAD_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['DOWNLOAD_SESSION_MIN_SLEEP'] = int(os.getenv('OFSC_DOWNLOAD_SESSION_MIN_SLEEP', '0'))


    # --- Dynamic Session Sleep Configuration (For Downloads: 403 Forbidden Errors) ---
    config["DOWNLOAD_SESSION_403_SLEEP_INIT"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_INIT", "4")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "80")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_MAX"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_MAX", "180")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_DECAY_THRESHOLD", "70")
    )
    config["DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_DOWNLOAD_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['DOWNLOAD_SESSION_403_MIN_SLEEP'] = int(os.getenv('OFSC_DOWNLOAD_SESSION_403_MIN_SLEEP', '0'))


    # --- Dynamic Session Sleep Configuration (For CDM: 429/504 Rate Limiting) ---
    config["CDM_SESSION_SLEEP_INIT"] = int(
        os.getenv("OFSC_CDM_SESSION_SLEEP_INIT", "0")
    )
    config["CDM_SESSION_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_CDM_SESSION_SLEEP_INCREASE_TIME_DIFF", "30")
    )
    config["CDM_SESSION_SLEEP_MAX"] = int(
        os.getenv("OFSC_CDM_SESSION_SLEEP_MAX", "180")
    )
    config["CDM_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["CDM_SESSION_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_CDM_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["CDM_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['CDM_SESSION_MIN_SLEEP'] = int(os.getenv('OFSC_CDM_SESSION_MIN_SLEEP', '4'))


    # --- Dynamic Session Sleep Configuration (For CDM: 403 Forbidden Errors) ---
    config["CDM_SESSION_403_SLEEP_INIT"] = int(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_INIT", "8")
    )
    config["CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "60")
    )
    config["CDM_SESSION_403_SLEEP_MAX"] = int(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_MAX", "180")
    )
    config["CDM_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["CDM_SESSION_403_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["CDM_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_CDM_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['CDM_SESSION_403_MIN_SLEEP'] = int(os.getenv('OFSC_CDM_SESSION_403_MIN_SLEEP', '0'))


    # --- Dynamic Session Sleep Configuration (For Like Operations: 429/504 Rate Limiting) ---
    config["LIKE_SESSION_SLEEP_INIT"] = int(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_INIT", "8")
    )
    config["LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_INCREASE_TIME_DIFF", "4")
    )
    config["LIKE_SESSION_SLEEP_MAX"] = int(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_MAX", "120")
    )
    config["LIKE_SESSION_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_INCREASE_FACTOR", "2.0")
    )
    config["LIKE_SESSION_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_DECAY_THRESHOLD", "120")
    )
    config["LIKE_SESSION_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['LIKE_SESSION_MIN_SLEEP'] = int(os.getenv('OFSC_LIKE_SESSION_MIN_SLEEP', '0'))


    # --- Dynamic Session Sleep Configuration (For Like Operations: 403 Forbidden Errors) ---
    config["LIKE_SESSION_403_SLEEP_INIT"] = int(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_INIT", "8")
    )
    config["LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF"] = int(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_INCREASE_TIME_DIFF", "4")
    )
    config["LIKE_SESSION_403_SLEEP_MAX"] = int(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_MAX", "120")
    )
    config["LIKE_SESSION_403_SLEEP_INCREASE_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_INCREASE_FACTOR", "1.5")
    )
    config["LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD"] = int(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_DECAY_THRESHOLD", "65")
    )
    config["LIKE_SESSION_403_SLEEP_DECAY_FACTOR"] = float(
        os.getenv("OFSC_LIKE_SESSION_403_SLEEP_DECAY_FACTOR", "1.5")
    )
    config['LIKE_SESSION_403_MIN_SLEEP'] = int(os.getenv('OFSC_LIKE_SESSION_403_MIN_SLEEP', '0'))

    

    # --- Miscellaneous ---
    # AUTH_WARNING_TIMEOUT: Time to wait between printing auth warnings (seconds).)
    config["AUTH_WARNING_TIMEOUT"] = float(
        os.getenv("OFSC_AUTH_WARNING_TIMEOUT", "1800")
    )

    return config
