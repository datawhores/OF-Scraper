import os


def load_other_urls_config():
    """
    Loads CDM URL and bad URL host configurations from environment variables with default values.

    Returns:
        A dictionary containing the loaded configuration settings.
    """
    config = {}

    # --- CDM URL Configuration ---
    # CDRM: URL for the CDM decryption API.
    # Default: "https://cdrm-project.com/api/decrypt"
    config["CDRM"] = os.getenv("OFSC_CDRM_URL", "https://cdrm-project.com/api/decrypt")

    # --- Bad URL Host Configuration ---
    # BAD_URL_HOST: A set of regular expression patterns for "bad" URL hosts.
    # Default: {".*\\.upload.onlyfans.com", "of2transcoder.s3-accelerate.amazonaws.com", ".*\\.convert.onlyfans.com"}
    # Expects a comma-separated string if provided via environment variable (e.g., "pattern1,pattern2")
    bad_url_host_env = os.getenv("OFSC_BAD_URL_HOSTS")
    if bad_url_host_env:
        # Split the string by comma and strip whitespace from each item, convert to a set
        config["BAD_URL_HOST"] = {host.strip() for host in bad_url_host_env.split(",")}
    else:
        config["BAD_URL_HOST"] = {
            ".*\\.upload.onlyfans.com",
            "of2transcoder.s3-accelerate.amazonaws.com",
            ".*\\.convert.onlyfans.com",
        }

    return config
