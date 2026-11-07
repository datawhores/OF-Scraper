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
import traceback

import httpx

import ofscraper.sites as sites
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.console as console
import ofscraper.utils.settings as settings
from . import me
from ofscraper.utils.auth.request import UnusableDynamicRule

log = logging.getLogger("shared")


def print_sign_status():
    status = getstatus()
    if status == "UP":
        console.get_shared_console().print("Status - [bold green]🟢 UP[/bold green]")
    else:
        console.get_shared_console().print("Status - [bold red]🔴 DOWN[/bold red]")


def _host(e: httpx.HTTPError) -> str:
    try:
        return e.request.url.host
    except RuntimeError:
        return "the server"


def unavailable_message(e: Exception) -> str | None:
    """
    Returns a message for a failure that says nothing about the auth
    (network errors, server errors, a reply that isn't JSON), else None.
    """
    if isinstance(e, httpx.TransportError):
        reason = (
            "timed out"
            if isinstance(e, httpx.TimeoutException)
            else "connection failed"
        )
        return f"Couldn't reach {_host(e)} ({reason}). Check your connection or VPN."
    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
        return f"{_host(e)} is rate limiting requests. Try again later."
    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code >= 500:
        return (
            f"{_host(e)} returned {e.response.status_code}: the server had an "
            "error. Try again later."
        )
    if isinstance(e, UnusableDynamicRule):
        return str(e)
    if isinstance(e, json.JSONDecodeError):
        # the parse error doesn't say which request it came from
        return (
            "Got a reply that isn't JSON from OnlyFans or the dynamic rule host. "
            "It may be a captive portal or a VPN block page, or the server may "
            "be having problems. Check your connection or VPN."
        )
    return None


def getstatus():
    if settings.get_settings().anon:
        return "UP"
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
            return "DOWN"
        return "UP"
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        message = unavailable_message(e)
        if message:
            log.error(message)
            return "UNAVAILABLE"
        return "DOWN"
