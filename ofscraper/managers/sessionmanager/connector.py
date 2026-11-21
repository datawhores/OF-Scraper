"""Requests waiting on a host lookup survive a clear of the saved addresses (#622).

aiohttp looks a host up once for every request that needs it at the same
moment: one asks, the rest wait, and each of them reads the saved answer when
it wakes, one turn of the loop later. ``clear_dns_cache`` in that turn leaves
nothing to read, and each waiting request fails with a KeyError.

The session clears the saved addresses when a host's requests must go to
another address (Fansly, #683) and when an address of the file host is left
(#620). A request that finds nothing saved looks the host up again.

Only the lookup changes here: no SSL setting and nothing sent to a server.
"""

import aiohttp

# how often one request looks a host up at most. Each clear costs a waiting
# request one more lookup, and clears are rare.
LOOKUPS = 10


class Connector(aiohttp.TCPConnector):
    # whatever else aiohttp passes is handed on as it is
    async def _resolve_host(self, host, port, *args, **kwargs):
        for _ in range(LOOKUPS - 1):
            try:
                return await super()._resolve_host(host, port, *args, **kwargs)
            except KeyError as E:
                # the saved addresses are kept by (host, port): this one was
                # cleared while the request waited on another's lookup
                if E.args != ((host, port),):
                    raise
        return await super()._resolve_host(host, port, *args, **kwargs)
