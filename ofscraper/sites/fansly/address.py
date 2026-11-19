"""Links signed for another address (#536).

Fansly signs a file link for the address the API request came from, and its
CDN refuses the link (403) from any other address. The API host has several
addresses. A VPN can send requests to some of them out through a different
exit than the rest of the traffic, downloads included. Every link in such a
response is then signed for an address the downloads don't come from.

The address range is readable in each link's policy, and it is the same for
every link of one response. So one link per range is tried on the CDN once.
A response whose range the CDN refuses is asked for again from the API
host's next address, and requests stay on the first address whose links the
CDN accepts. Until a response is refused, nothing changes.

Nothing here logs an address, a policy or a link.
"""

import base64
import binascii
import json
import logging
import socket
from urllib.parse import parse_qs, urlsplit

from aiohttp.abc import AbstractResolver
from aiohttp.resolver import DefaultResolver

log = logging.getLogger("shared")

# address range -> whether the CDN accepts links signed for it
_accepted = {}
# host -> which of its addresses (in sorted order) requests go to
_steered = {}
_told = False


def reset():
    global _told
    _accepted.clear()
    _steered.clear()
    _told = False


def _range(url):
    """The address range a link is signed for, or None."""
    try:
        policy = parse_qs(urlsplit(url).query).get("Policy", [None])[0]
        if not policy:
            return None
        # CloudFront's URL-safe base64
        policy = policy.replace("-", "+").replace("_", "=").replace("~", "/")
        policy += "=" * (-len(policy) % 4)
        statement = json.loads(base64.b64decode(policy))["Statement"][0]
        return statement["Condition"]["IpAddress"]["AWS:SourceIp"] or None
    except (
        binascii.Error,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        AttributeError,
    ):
        return None


def link_ranges(data) -> dict:
    """Each address range the response's links are signed for, with one such link."""
    found = {}
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            location = item.get("location")
            if isinstance(location, str):
                signed_for = _range(location)
                if signed_for:
                    found.setdefault(signed_for, location)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


async def _cdn_accepts(c, url):
    """True or False, or None when the try itself failed."""
    # imported here: the session manager imports this module for its resolver
    from ofscraper.managers.sessionmanager.sessionmanager import (
        HEADERS,
        is_provided_exception_number,
    )

    try:
        async with c.requests_async(
            url=url,
            headers={"Range": "bytes=0-0"},
            actions=[HEADERS],
            exceptions=[],
            retries=1,
        ):
            return True
    except Exception as E:
        if is_provided_exception_number(E, 403):
            return False
        log.debug(f"Fansly: could not try a signed link on the CDN: {type(E).__name__}")
        return None


async def usable(c, data) -> bool:
    """False when the response's links are signed for an address the CDN refuses."""
    global _told
    for signed_for, url in link_ranges(data).items():
        if signed_for not in _accepted:
            verdict = await _cdn_accepts(c, url)
            if verdict is None:
                continue
            _accepted[signed_for] = verdict
        if not _accepted[signed_for]:
            if not _told:
                _told = True
                log.info(
                    "Fansly signed some links for another address than the one "
                    "its CDN sees (this happens on some VPNs). Asking for those "
                    "again"
                )
            return False
    return True


def try_next_address(c, url):
    """Send the next requests for ``url``'s host to its next address."""
    host = urlsplit(url).hostname
    _steered[host] = _steered[host] + 1 if host in _steered else 0
    # the session keeps the host's addresses for a while and takes them in turn
    clear = getattr(c, "clear_dns_cache", None)
    if clear:
        clear()


def forget_refused():
    """Try the refused ranges again next time: this machine's address may
    have changed to one of them."""
    for signed_for in [k for k, ok in _accepted.items() if not ok]:
        del _accepted[signed_for]


def steer(host, addresses):
    """The one address requests to ``host`` go to, once a response from it
    was refused; before that, all of them."""
    if host not in _steered or not addresses:
        return addresses
    ordered = sorted(addresses, key=lambda a: a["host"])
    return [ordered[_steered[host] % len(ordered)]]


class Resolver(AbstractResolver):
    """The default resolver, with ``steer`` applied to its answers."""

    def __init__(self):
        self._default = DefaultResolver()

    async def resolve(self, host, port=0, family=socket.AF_INET):
        return steer(host, await self._default.resolve(host, port, family))

    async def close(self):
        await self._default.close()
