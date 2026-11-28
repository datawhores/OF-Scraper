r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import json
import logging
import ssl
import traceback

import aiohttp
import httpx

import ofscraper.sites as sites
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.console as console
import ofscraper.utils.settings as settings
from . import me
from ofscraper.utils.auth.request import DynamicRuleUnavailable

log = logging.getLogger("shared")


def print_sign_status():
    status = getstatus()
    if status == "UP":
        console.get_shared_console().print("Status - [bold green]🟢 UP[/bold green]")
    elif status == "UNAVAILABLE":
        # a network or server problem, already logged: says nothing about the auth
        console.get_shared_console().print(
            "Status - [bold yellow]🟡 Couldn't check[/bold yellow]"
        )
    else:
        console.get_shared_console().print("Status - [bold red]🔴 DOWN[/bold red]")


def _host(e: Exception) -> str:
    try:
        if isinstance(e, aiohttp.ClientResponseError):
            return e.request_info.url.host
        if isinstance(e, aiohttp.ClientConnectorError):
            return e.host
        return e.request.url.host
    except (AttributeError, RuntimeError):
        return "the server"


def _cert_error(e: BaseException) -> ssl.SSLCertVerificationError | None:
    """The certificate verification failure behind e, if there is one."""
    seen = set()
    while e is not None and id(e) not in seen:
        # aiohttp's ClientConnectorCertificateError is an
        # SSLCertVerificationError too, but the details are on the one it wraps
        if isinstance(e, ssl.SSLCertVerificationError) and not isinstance(
            e, aiohttp.ClientError
        ):
            return e
        seen.add(id(e))
        e = getattr(e, "certificate_error", None) or e.__cause__ or e.__context__
    return None


def _aiohttp_total_timeout(e: BaseException) -> bool:
    """
    aiohttp raises a bare TimeoutError when a request's total timeout runs
    out. Other code (asyncio.wait_for, subprocesses) raises the same type,
    so only one raised inside aiohttp counts.
    """
    if type(e) is not TimeoutError:
        return False
    tb = e.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb is not None and tb.tb_frame.f_globals.get("__name__", "").startswith(
        "aiohttp."
    )


def unavailable_message(e: Exception) -> str | None:
    """
    Returns a message for a failure that says nothing about the auth
    (network errors, server errors, a reply that isn't JSON), else None.
    Covers httpx (the auth check) and aiohttp (the async session) errors.
    """
    if isinstance(e, aiohttp.ClientHttpProxyError):
        # the proxy refused the tunnel (407 = it wants a login): the status is
        # the proxy's, not the server's
        return (
            f"Couldn't reach {_host(e)} through the proxy (connection failed). "
            f"Check your proxy settings. Error: the proxy answered {e.status} "
            f"{e.message}".rstrip()
        )
    if isinstance(
        e,
        (httpx.TransportError, aiohttp.ClientConnectionError, aiohttp.ClientPayloadError),
    ) or _aiohttp_total_timeout(e):
        cert_error = _cert_error(e)
        if cert_error:
            # the server was reached: the connection isn't the problem
            return (
                f"Couldn't verify the certificate of {_host(e)} "
                f"({cert_error.verify_message}). A proxy, VPN or antivirus may be "
                "intercepting HTTPS, or this Python has no CA certificates."
            )
        timed_out = isinstance(
            e, (httpx.TimeoutException, aiohttp.ServerTimeoutError)
        ) or _aiohttp_total_timeout(e)
        reason = "timed out" if timed_out else "connection failed"
        message = f"Couldn't reach {_host(e)} ({reason}). Check your connection or VPN."
        # the cause (DNS, refused, reset, proxy, TLS) is otherwise only in the
        # debug log
        detail = " ".join(str(e).split())[:200]
        if detail and not timed_out:
            message += f" Error: {detail}"
        return message
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
    elif isinstance(e, aiohttp.ClientResponseError):
        status = e.status
    else:
        status = None
    if status == 429:
        return f"{_host(e)} is rate limiting requests. Try again later."
    if status is not None and status >= 500:
        return (
            f"{_host(e)} returned {status}: the server had an "
            "error. Try again later."
        )
    if isinstance(e, DynamicRuleUnavailable):
        return str(e)
    # aiohttp's json() refuses a reply that isn't labelled JSON. A 4xx one
    # is left to the auth check, like any other 4xx
    if isinstance(e, json.JSONDecodeError) or (
        isinstance(e, aiohttp.ContentTypeError) and e.status < 400
    ):
        # the parse error doesn't say which request it came from
        return (
            "Got a reply that isn't JSON from OnlyFans or the dynamic rule host. "
            "It may be a captive portal or a VPN block page, or the server may "
            "be having problems. Check your connection or VPN."
        )
    return None


def getstatus():
    return auth_status()[0]


def auth_status():
    """
    Returns (status, message). status is UP, DOWN (the auth was rejected) or
    UNAVAILABLE (the auth couldn't be checked, including a 4xx other than 400
    or 401, which is usually a block). message says why it couldn't
    be checked, for callers with no log to point to (a GUI dialog); it's None
    for UP and DOWN.
    """
    if settings.get_settings().anon:
        return "UP", None
    try:
        # fetch the dynamic rule once, with its own retries. Otherwise each
        # retry of /me fetches it again, retries included. Fansly requests
        # aren't signed with it, so a Fansly profile doesn't fetch it
        if not sites.is_fansly():
            auth_requests.get_request_auth()
        data = me.scrape_user()
        # /me answers isAuth false when no one is logged in. That's a normal
        # answer for anonymous runs, so it's only treated as bad auth here
        if not data.get("isAuth"):
            log.info("OnlyFans says this session isn't logged in")
            return "DOWN", None
        return "UP", None
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        message = unavailable_message(e) or _refused_message(e)
        if message:
            log.error(message)
            return "UNAVAILABLE", message
        return "DOWN", None


def _refused_message(e: Exception) -> str | None:
    """Only 400 and 401 (the statuses the session treats as auth errors) say
    the login is bad. Another 4xx on /me, such as a 403 from a firewall or a
    ban, isn't fixed by new auth."""
    from ofscraper.utils.checkers import http_status

    status = http_status(e)
    if status is None or not 400 <= status < 500 or status in (400, 401):
        return None
    return (
        f"{_host(e)} refused the login check with {status}. That's usually a "
        "block (a firewall, VPN or ban), not a rejected login."
    )
