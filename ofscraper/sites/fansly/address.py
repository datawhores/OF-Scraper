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

The accepted links are kept, up to ``WITNESSES`` per range (the second is
tried from a later response, so it is another post's file). They are what a
later refusal is checked against: their files were there, a refused file may
just be deleted.

Nothing here logs an address, a policy or a link.
"""

import base64
import binascii
import json
import logging
import socket
import time
from urllib.parse import parse_qs, urlsplit

from aiohttp.abc import AbstractResolver
from aiohttp.resolver import DefaultResolver

log = logging.getLogger("shared")

# address range -> whether the CDN accepts links signed for it
_accepted = {}
# address range -> links signed for it that the CDN accepted, each of another
# file and from another response, newest last
_witness = {}
WITNESSES = 2
# a kept link this close to running out (seconds) is not tried again
WITNESS_MARGIN = 60
# host -> which of its addresses (in sorted order) requests go to
_steered = {}
_told = False


def reset():
    global _told
    _accepted.clear()
    _witness.clear()
    _steered.clear()
    _told = False


_UNREADABLE = (
    binascii.Error,
    ValueError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
)


def _condition(url):
    """The conditions a link's policy sets (a dict), or None."""
    try:
        policy = parse_qs(urlsplit(url).query).get("Policy", [None])[0]
        if not policy:
            return None
        # CloudFront's URL-safe base64
        policy = policy.replace("-", "+").replace("_", "=").replace("~", "/")
        policy += "=" * (-len(policy) % 4)
        return json.loads(base64.b64decode(policy))["Statement"][0]["Condition"]
    except _UNREADABLE:
        return None


def _range(url):
    """The address range a link is signed for, or None."""
    try:
        return _condition(url)["IpAddress"]["AWS:SourceIp"] or None
    except _UNREADABLE:
        return None


def _run_out(url) -> bool:
    """True when the link's policy ends within ``WITNESS_MARGIN`` seconds."""
    try:
        return float(_condition(url)["DateLessThan"]["AWS:EpochTime"]) <= (
            time.time() + WITNESS_MARGIN
        )
    except _UNREADABLE:
        return False


def _kept(signed_for, but=None):
    """The kept links of a range that haven't run out, without the one of
    ``but``'s file."""
    path = urlsplit(but).path if but else None
    return [
        url
        for url in _witness.get(signed_for, ())
        if not _run_out(url) and urlsplit(url).path != path
    ]


def _wanted(signed_for, url) -> bool:
    """True when fewer than ``WITNESSES`` links are kept for the range and
    ``url`` is of a file none of them is of."""
    kept = _kept(signed_for)
    return len(kept) < WITNESSES and len(_kept(signed_for, url)) == len(kept)


def _keep(signed_for, url, verdict):
    """What the CDN said about ``url``, a link signed for ``signed_for``."""
    _accepted[signed_for] = verdict
    if verdict:
        _witness[signed_for] = [*_kept(signed_for, url), url][-WITNESSES:]
    else:
        _witness.pop(signed_for, None)


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
            _keep(signed_for, url, verdict)
        elif _accepted[signed_for] and _wanted(signed_for, url):
            # a link of another file, from a later response. A refusal of it
            # decides nothing: that file may be gone
            if await _cdn_accepts(c, url):
                _keep(signed_for, url, True)
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


def link_range(url):
    """The address range ``url`` is signed for, or None (never logged)."""
    return _range(url) if url else None


async def cdn_refuses(c, url):
    """True when the CDN refuses ``url`` (one byte is asked for), False when
    it accepts it, None when the try itself failed. Changes nothing here."""
    verdict = await _cdn_accepts(c, url)
    return None if verdict is None else not verdict


async def try_link(c, url):
    """Try ``url`` on the CDN (one byte) and keep what it says about the
    range it is signed for. Returns True when the CDN accepts it, False when
    it refuses it, None when the try itself failed or the link has no range."""
    signed_for = _range(url) if url else None
    if not signed_for:
        return None
    verdict = await _cdn_accepts(c, url)
    if verdict is not None:
        _keep(signed_for, url, verdict)
    return verdict


def accepted_links(url):
    """The links of other files that the CDN accepted earlier, signed for
    the same range as ``url``, newest first; none when none is kept or they
    have run out.

    Those files were there then, so what the CDN says to them now is about
    the range: a link of a file that may be deleted says nothing. One of
    them may be deleted since, so the range is refused only when all are."""
    signed_for = _range(url) if url else None
    return _kept(signed_for, url)[::-1] if signed_for else []


def gone(url):
    """``url`` is kept no longer: the CDN refuses it and accepts another
    link of its range, so its file was deleted."""
    signed_for = _range(url) if url else None
    if signed_for in _witness:
        _witness[signed_for] = [u for u in _witness[signed_for] if u != url]


def refused(url):
    """The CDN refuses links signed for the range ``url`` is signed for (the
    caller has the evidence: ``accepted_links`` are refused now, or the file's
    new link, signed for another range, is accepted).

    The address downloads leave from changed (a VPN switch), so every link
    signed for the old range is refused, those of files not started yet
    included. This is newer evidence about the range than the API probe had,
    so it replaces it. It is one fact, and it is tested again whenever a new
    link signed for the range arrives (``try_link``, ``usable`` after
    ``forget_refused``). Links without a range change nothing.
    """
    signed_for = _range(url)
    if signed_for:
        _keep(signed_for, url, False)


def is_refused(url) -> bool:
    """True when ``url`` is signed for a range the CDN refuses."""
    signed_for = _range(url) if url else None
    return bool(signed_for) and _accepted.get(signed_for) is False


def is_accepted(url) -> bool:
    """True when ``url`` is signed for a range the CDN is known to accept."""
    signed_for = _range(url) if url else None
    return bool(signed_for) and _accepted.get(signed_for) is True

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
