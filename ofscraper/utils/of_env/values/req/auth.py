import os


def load_auth_config():
    config = {}
    # AUTH_WARNING_TIMEOUT: Minimum time, in seconds, between repeated auth warning messages.
    config["AUTH_WARNING_TIMEOUT"] = float(
        os.getenv("OFSC_AUTH_WARNING_TIMEOUT", "1800")
    )
    return config
