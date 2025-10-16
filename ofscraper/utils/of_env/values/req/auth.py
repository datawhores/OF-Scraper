import os


def load_misc_config():
    config = {}
    # AUTH_WARNING_TIMEOUT: Time to wait between printing auth warnings (seconds).)
    config["AUTH_WARNING_TIMEOUT"] = float(
        os.getenv("OFSC_AUTH_WARNING_TIMEOUT", "1800")
    )
    return config
