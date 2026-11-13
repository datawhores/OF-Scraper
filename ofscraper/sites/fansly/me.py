"""Token check (``account/me``) and the device id Fansly's signed headers need."""

import logging

import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import constants
from ofscraper.sites.fansly import headers as fansly_headers

log = logging.getLogger("shared")


class FanslyAuthError(Exception):
    pass


def unwrap(data):
    """Payload of Fansly's ``{"success": true, "response": ...}`` envelope."""
    if not isinstance(data, dict) or str(data.get("success")).lower() != "true":
        raise FanslyAuthError("Fansly answered without success")
    return data.get("response")


def fetch_device_id(c) -> str:
    """``GET device/id``, sent without the token or signed headers."""
    auth = fansly_auth.read_auth()
    with c.requests(
        constants.DEVICE_ID_URL, headers=fansly_headers.cdn_headers(auth), actions=[]
    ) as r:
        device_id = unwrap(r.json_())
    if not isinstance(device_id, (str, int)) or not str(device_id).strip():
        raise FanslyAuthError("Fansly returned no device id")
    return str(device_id).strip()


def ensure_device_id(c) -> dict:
    auth = fansly_auth.read_auth()
    if fansly_auth.device_id_is_fresh(auth):
        return auth
    return fansly_auth.store_device_id(fetch_device_id(c))


def parse_me(data) -> dict:
    """OF-Scraper's "me" shape (id, username, name, isAuth) from ``account/me``."""
    account = (unwrap(data) or {}).get("account") or {}
    username = account.get("username")
    if not username:
        raise FanslyAuthError("account/me returned no username; the token is not valid")
    return {
        "id": account.get("id"),
        "username": username,
        "name": account.get("displayName") or username,
        "isAuth": True,
    }


def scrape_user(c=None):
    """Check the token with ``account/me`` and return the signed-in account."""
    if c is None:
        import ofscraper.managers.manager as manager

        with manager.Manager.session.get_ofsession() as c:
            return scrape_user(c)
    ensure_device_id(c)
    with c.requests(constants.ME_URL) as r:
        if r.status_code == 401:
            raise FanslyAuthError("Fansly rejected the token (401)")
        data = parse_me(r.json_())
    sensitive.add_sensitive_pattern(str(data["id"]), "userid")
    sensitive.add_sensitive_pattern(
        f"{data['username']} | {data['username']}|\\b{data['username']}\\b", "username"
    )
    return data
