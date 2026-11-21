"""A host's addresses, kept for a while and handed out in turn (#622).

aiohttp does this itself: it looks a host up once for every request that
needs it at the same moment, keeps the answer, and gives each new connection
the addresses starting one further on. But the requests that wait on a
lookup read the kept answer one turn of the loop after it was kept, and a
clear in that turn (``clear_dns_cache``) leaves nothing to read: each of
them fails with a KeyError.

The session clears the kept addresses when a host's requests must go to
another address (Fansly, #683) and when an address of the file host is left
(#620). So the keeping is done here and aiohttp's own is off
(``use_dns_cache=False``). A waiting request is handed the answer itself.
After a clear in that turn, the request that asked uses the answer and each
one that waited looks the host up again, so it gets addresses from after the
clear.

Why not aiohttp's own cache with a patch around it: the only place to catch
the KeyError is a private aiohttp method. A later aiohttp could rename it,
and the patch would stop applying without any error. This uses only what
aiohttp documents (a resolver, and ``use_dns_cache``). When an aiohttp
release has the fix (aio-libs/aiohttp#14427), aiohttp's own cache can be
used again and this module removed.

Only lookups change here: no SSL setting and nothing sent to a server.
"""

import asyncio
import socket
import time

from aiohttp.abc import AbstractResolver

# how long an answer is kept (seconds): aiohttp's own default
KEPT = 10
# how many lookups one request waits on when each is followed by a clear
# before the request reads it. After that it uses the last answer
LOOKUPS = 10


class Resolver(AbstractResolver):
    """``inner``'s answers, kept for ``kept`` seconds. Each call is given the
    addresses starting one further on, so connections spread over them."""

    def __init__(self, inner, kept=KEPT):
        self._inner = inner
        self._kept = kept
        # (host, port, family) -> [addresses, when looked up, calls so far]
        self._answers = {}
        # (host, port, family) -> the last lookup started. One that has
        # ended stays until the next takes its place
        self._lookups = {}

    async def resolve(self, host, port=0, family=socket.AF_INET):
        key = (host, port, family)
        for _ in range(LOOKUPS):
            answer = self._answers.get(key)
            if answer is not None and answer[1] + self._kept >= time.monotonic():
                break
            lookup = self._lookups.get(key)
            asked = lookup is None or lookup.done()
            if asked:
                lookup = asyncio.ensure_future(self._look_up(key))
                self._lookups[key] = lookup
                lookup.add_done_callback(self._done)
            # a request that is cancelled doesn't take the lookup, which
            # others wait on, with it
            answer = await asyncio.shield(lookup)
            # cleared since the answer came: only the request that asked
            # uses it
            if asked or self._answers.get(key) is answer:
                break
        addresses, _, calls = answer
        answer[2] += 1
        at = calls % len(addresses) if addresses else 0
        return addresses[at:] + addresses[:at]

    async def _look_up(self, key):
        host, port, family = key
        addresses = await self._inner.resolve(host, port, family=family)
        answer = self._answers[key] = [list(addresses), time.monotonic(), 0]
        return answer

    @staticmethod
    def _done(lookup):
        # a lookup that failed after its requests were cancelled has no one
        # to raise to
        if not lookup.cancelled():
            lookup.exception()

    def clear(self):
        """Look every host up again the next time it is asked for."""
        self._answers.clear()

    async def close(self):
        for lookup in list(self._lookups.values()):
            lookup.cancel()
        await self._inner.close()
