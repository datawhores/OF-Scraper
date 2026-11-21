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
hold the one that was left. A kept-alive connection to it that is still in
a pool is closed when a request comes to use it, before anything is sent,
and that request goes over another connection (``Request``). When every
address of a host has refused, all are used again.

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
    no longer tells its address.

    A connection that answered 403 isn't kept. Where connections are used
    again (#556) it would be the next one handed out, so the request made
    after a refusal, and most that follow, would go to the same address
    whether or not that address is left."""

    came_over = None
    came_from = None

    async def start(self, connection):
        self.came_over = connection.transport
        peer = self.came_over and self.came_over.get_extra_info("peername")
        self.came_from = peer[0] if peer else None
        protocol = connection.protocol
        await super().start(connection)
        if self.status == 403:
            if self.connection is None:
                # the whole answer is in and the connection back in the pool
                if self.came_over is not None:
                    self.came_over.close()
            elif protocol is not None:
                # closed, not kept, once the answer is read
                protocol.force_close()
        return self


class Request(aiohttp.ClientRequest):
    """Sends nothing over a connection to an address that was left: a
    kept-alive one opened before then, or a new one made from addresses
    saved before then. aiohttp closes the connection this fails on and sends
    the request again, once; after that the session's own retries do."""

    async def send(self, conn):
        if goes_to_one_left(self.url.host, conn.transport):
            raise aiohttp.ServerDisconnectedError(
                "the connection is to an address that is no longer used"
            )
        return await super().send(conn)


def goes_to_one_left(host, transport) -> bool:
    """True when ``transport`` is a connection to an address of ``host``
    that was left."""
    peer = transport and transport.get_extra_info("peername")
    return bool(peer) and peer[0] in _refusing.get(host, ())


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
