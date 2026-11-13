"""Headers for Fansly requests.

API calls (``apiv3.fansly.com``) carry the token and the signed bundle
(``fansly-client-id``, ``fansly-client-ts``, ``fansly-client-check`` and, when
the token reveals it, ``fansly-session-id``). Everything else, CDN files and
playlists included, carries only the browser-like headers: no token, no
signing, no cookies.
"""

import logging
from urllib.parse import urlparse

from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import constants, signing

log = logging.getLogger("shared")


def is_api_url(url) -> bool:
    return urlparse(str(url or "")).netloc.lower() == urlparse(constants.API_BASE).netloc.lower()


def browser_headers(auth: dict) -> dict:
    return {
        "User-Agent": auth.get("user_agent") or "",
        "Origin": constants.ORIGIN,
        "Referer": constants.REFERER,
        "Accept-Language": constants.ACCEPT_LANGUAGE,
        "Accept": constants.ACCEPT,
    }


def api_headers(url, auth: dict, clock=None) -> dict:
    clock = clock or signing.client_ts
    headers = browser_headers(auth)
    headers["authorization"] = auth.get("authorization_token") or ""
    device_id = auth.get("device_id")
    if device_id:
        headers["fansly-client-id"] = device_id
        headers["fansly-client-ts"] = str(clock())
        headers["fansly-client-check"] = signing.client_check(
            url, fansly_auth.check_key(auth), device_id
        )
    else:
        log.debug("no Fansly device id yet; sending the request without the signed headers")
    sid = fansly_auth.session_id(auth.get("authorization_token"))
    if sid:
        headers["fansly-session-id"] = sid
    return headers


def cdn_headers(auth: dict) -> dict:
    return browser_headers(auth)


def make_headers(url, auth=None) -> dict:
    auth = auth if auth is not None else fansly_auth.read_auth()
    return api_headers(url, auth) if is_api_url(url) else cdn_headers(auth)
