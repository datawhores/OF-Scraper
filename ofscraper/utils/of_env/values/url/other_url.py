import os


def load_other_urls_config():
    """
    Loads CDM URL and bad URL host configurations from environment variables with default values.

    Returns:
        A dictionary containing the loaded configuration settings.
    """
    config = {}

    # --- CDM URL Configuration ---
    # CDRM: URL of a self-hosted decryption server for the deprecated `cdrm` key mode. It is sent the request headers, cookies included. The default, `cdrm-project.com`, isn't contacted: protected videos are skipped before download, with a message to use `manual` key mode. The same happens when the value isn't an http or https address with a host (it isn't printed). Set it only to a server you run yourself.
    # Default: "https://cdrm-project.com/api/decrypt"
    config["CDRM"] = os.getenv("OFSC_CDRM_URL", "https://cdrm-project.com/api/decrypt")

    # --- Bad URL Host Configuration ---
    # BAD_URL_HOST: Regular expressions for hosts whose media is skipped and recorded in the database as downloaded with no file (a comma-separated list can be given in `OFSC_BAD_URL_HOSTS`).
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

    # --- Media Host Configuration ---
    # MEDIA_HOST_SUFFIXES: Domains added to onlyfans.com, the hosts that may be sent the OnlyFans login with a download.
    # Default: []
    # Expects a comma-separated string if provided via environment variable (e.g., "cdn.example.com,example.net")
    media_host_env = os.getenv("OFSC_MEDIA_HOST_SUFFIXES")
    config["MEDIA_HOST_SUFFIXES"] = (
        [host.strip() for host in media_host_env.split(",") if host.strip()]
        if media_host_env
        else []
    )

    return config
