"""Hosts that may be sent the OnlyFans login with a download.

OnlyFans downloads carry the session cookies and the signed login headers,
and DRM segments carry the cookies in their Cookie header. They go only to
hosts under these domains, over http or https. A host matches a domain or a
subdomain of it on a dot boundary: cdn2.onlyfans.com does, evil-onlyfans.com
and onlyfans.com.evil.example don't. MEDIA_HOST_SUFFIXES
(OFSC_MEDIA_HOST_SUFFIXES) adds domains.

Fansly isn't checked: its token goes to its API host only, never to a file's
host (sites/fansly/headers.py).
"""

import logging
from urllib.parse import urlsplit

import ofscraper.sites as sites
import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")

DEFAULT_SUFFIXES = ("onlyfans.com",)

# download_session fills an empty action list with its defaults (cookies,
# login headers and signing); a list naming none of them sends none
NO_CREDENTIALS = ["no_credentials"]

# hosts already warned about: a creator can have many files on one host
_warned = set()


class RefusedHost(Exception):
    """A request that would send the login to a host outside the list."""


def suffixes():
    extra = of_env.getattr("MEDIA_HOST_SUFFIXES") or []
    if isinstance(extra, str):
        extra = extra.split(",")
    cleaned = (str(s).strip().lower().lstrip("*.").rstrip(".") for s in extra)
    return DEFAULT_SUFFIXES + tuple(s for s in cleaned if s)


def _host(url):
    """The host of an http(s) URL, or None."""
    try:
        parts = urlsplit(str(url or "").strip())
        host = parts.hostname
    except ValueError:
        return None
    # a backslash in the address part is read differently by different
    # parsers, so which host gets the request isn't certain
    if parts.scheme.lower() not in ("http", "https") or "\\" in parts.netloc:
        return None
    return host.rstrip(".") if host else None


def _shown(url):
    """The host for a log message; never the whole (signed) link."""
    host = _host(url)
    if host:
        return host
    try:
        parts = urlsplit(str(url or "").strip())
        return parts.hostname or f"a {parts.scheme or 'schemeless'} link"
    except ValueError:
        return "an unreadable link"


def is_allowed(url):
    host = _host(url)
    return bool(host) and any(host == s or host.endswith("." + s) for s in suffixes())


def ensure_allowed_download_url(url, kind="media"):
    """url, or RefusedHost (logged with the host only) when it's outside the list."""
    if is_allowed(url):
        return url
    message = (
        f"{kind} not downloaded: {_shown(url)} isn't an allowed host for the "
        "OnlyFans login. If it is a real media host, add it to "
        "OFSC_MEDIA_HOST_SUFFIXES"
    )
    log.warning(message)
    raise RefusedHost(message)


def drop_login_on_redirect(url, login):
    """An aiohttp client middleware for a request to url that carries the
    login headers named in login. aiohttp follows redirects itself, and on the
    way to another host it drops only the cookies, so a host outside the list
    would get the rest. A redirect to such a host is sent without them. The
    first request, redirects on its own host and to allowed hosts go as before."""
    first = _host(url)
    login = tuple(login)

    async def middleware(req, handler):
        target = str(req.url)
        if _host(target) != first and not is_allowed(target):
            for name in login:
                req.headers.popall(name, None)
            host = _shown(target)
            if host not in _warned:
                _warned.add(host)
                log.warning(
                    f"a request was redirected to {host}, which isn't an allowed "
                    "host for the OnlyFans login: it is sent without it. If it "
                    "needs the login, add it to OFSC_MEDIA_HOST_SUFFIXES"
                )
        return await handler(req)

    return middleware


def download_actions(url):
    """The session actions for a plain file download from url. None keeps the
    download session's defaults, which send the OnlyFans login. A host
    outside the list gets the request without it, so the file still
    downloads: its link is signed and doesn't need the login."""
    if sites.is_fansly() or is_allowed(url):
        return None
    host = _shown(url)
    if host not in _warned:
        _warned.add(host)
        log.warning(
            f"{host} isn't an allowed host for the OnlyFans login: its files are "
            "downloaded without it. If it needs the login, add it to "
            "OFSC_MEDIA_HOST_SUFFIXES"
        )
    return NO_CREDENTIALS
