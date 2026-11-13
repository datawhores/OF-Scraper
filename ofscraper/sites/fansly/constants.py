import os

API_HOST = "apiv3.fansly.com"
API_BASE = os.getenv("OFSC_FANSLY_API_BASE", f"https://{API_HOST}/api/v1/")
ORIGIN = "https://fansly.com"
REFERER = "https://fansly.com/"
ACCEPT = "application/json, text/plain, */*"
ACCEPT_LANGUAGE = "en-US,en;q=0.9"

# Fallback used when the auth file has no check key. Fansly rotates this value
# when it deploys a new web app; put the current one in fansly_auth.json.
DEFAULT_CHECK_KEY = "oybZy8-fySzis-bubayf"

# device ids are refreshed after this long
DEVICE_ID_MAX_AGE_SECONDS = 180 * 60

AUTH_FILE = os.getenv("OFSC_FANSLY_AUTH_FILE_NAME", "fansly_auth.json")


def api_url(path: str) -> str:
    """Full API URL; every GET carries ``ngsw-bypass=true`` like the web app."""
    url = API_BASE + path.lstrip("/")
    return url + ("&" if "?" in url else "?") + "ngsw-bypass=true"


ME_URL = api_url("account/me")
DEVICE_ID_URL = api_url("device/id")
