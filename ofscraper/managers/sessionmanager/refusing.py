"""An address of the file host that refuses links its other addresses take (#620).

OnlyFans' file host answers at several addresses. One of them can refuse
(403) every signed link while the others take the same links. Which address
a download goes to is the connection pool's choice, so some files of a run
were refused, a different one each time, and a second run got them.

A link that ran out, or one signed for another address than this machine's,
is refused the same way, by every address. So an address is at fault only
when the site still gives the link it refused (the downloader asks, see
``refresh_media_link``). Such an address isn't used again while the host has
another: the connection the refusal came over is closed (a later request
could reuse it), and the address is left out of the host's addresses, which
is what new connections are made from. Every session then looks hosts up
again before its next request (``times_left``): the addresses it saved may
hold the one that was left. When every address of a host has refused, all
are used again.

Nothing here logs an address.
"""

import aiohttp
from aiohttp.abc import AbstractResolver

# host -> its addresses that refused a link the site still gave
_refusing = {}
# how many times an address was left
_left = 0


def reset():
    global _left
    _refusing.clear()
    _left = 0


def times_left() -> int:
    """Goes up each time an address is left. A session that saved a host's
    addresses before then may still hold that address."""
    return _left


class Response(aiohttp.ClientResponse):
    """Remembers the connection it came over and the address at its other
    end. A refusal's body is short: by the time it is seen, the connection
    is back in the pool, and when its session has closed (a protected
    video's manifest is read through a session of its own), the connection
    no longer tells its address."""

    came_over = None
    came_from = None

    async def start(self, connection):
        self.came_over = connection.transport
        peer = self.came_over and self.came_over.get_extra_info("peername")
        self.came_from = peer[0] if peer else None
        return await super().start(connection)


def leave(response) -> bool:
    """Close the connection ``response`` came over and leave its address out
    of the host's addresses. True when that changed the host's addresses."""
    global _left
    transport = getattr(response, "came_over", None)
    if transport is not None:
        transport.close()
    address = getattr(response, "came_from", None)
    host = response.url.host
    if not address or not host:
        return False
    refusing = _refusing.setdefault(host, set())
    if address in refusing:
        return False
    refusing.add(address)
    _left += 1
    return True


def without(host, addresses):
    """``addresses`` of ``host`` without those that were left."""
    refusing = _refusing.get(host)
    if not refusing:
        return addresses
    left = [a for a in addresses if a["host"] not in refusing]
    if left:
        return left
    # every address was left: it wasn't about the address
    _refusing.pop(host, None)
    return addresses


class Resolver(AbstractResolver):
    """``inner``, with ``without`` applied to its answers."""

    def __init__(self, inner):
        self._inner = inner

    async def resolve(self, host, port=0, **kwargs):
        return without(host, await self._inner.resolve(host, port, **kwargs))

    async def close(self):
        await self._inner.close()
