"""Request signing values the Fansly web app sends with API calls.

``fansly-client-check`` is a cyrb53 digest of ``<check key>_<url path>_<device id>``.
cyrb53 is a public-domain 53-bit string hash (by bryc); this is a plain Python
port of its published form, using JavaScript's 32-bit multiply semantics over
UTF-16 code units.
"""

import threading
import time
from urllib.parse import urlparse

_MASK32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & _MASK32


def _utf16_units(text: str):
    data = text.encode("utf-16-le", "surrogatepass")
    for i in range(0, len(data), 2):
        yield data[i] | (data[i + 1] << 8)


def cyrb53(text: str, seed: int = 0) -> int:
    h1 = (0xDEADBEEF ^ seed) & _MASK32
    h2 = (0x41C6CE57 ^ seed) & _MASK32
    for ch in _utf16_units(text):
        h1 = _imul(h1 ^ ch, 2654435761)
        h2 = _imul(h2 ^ ch, 1597334677)
    h1 = _imul(h1 ^ (h1 >> 16), 2246822507)
    h1 ^= _imul(h2 ^ (h2 >> 13), 3266489909)
    h2 = _imul(h2 ^ (h2 >> 16), 2246822507)
    h2 ^= _imul(h1 ^ (h1 >> 13), 3266489909)
    return 4294967296 * (2097151 & h2) + (h1 & _MASK32)


def client_check(url: str, check_key: str, device_id: str) -> str:
    """Digest for the ``fansly-client-check`` header: path only, no host or query."""
    path = urlparse(url).path
    return format(cyrb53(f"{check_key}_{path}_{device_id}"), "x")


class ClientClock:
    """Milliseconds for ``fansly-client-ts`` that never go backwards."""

    def __init__(self, now=time.time):
        self._now = now
        self._last = 0
        self._lock = threading.Lock()

    def __call__(self) -> int:
        with self._lock:
            value = max(int(self._now() * 1000), self._last)
            self._last = value
            return value


client_ts = ClientClock()
