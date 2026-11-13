"""
Pin the TLS ClientHello that create_custom_ssl_context() produces.

The ClientHello is captured through each transport that uses the context: a
raw socket, httpx (sync, HTTP/2) and aiohttp (async). Transports differ, e.g.
httpx adds ALPN. This covers the "custom" ssl_verify mode only; the "default"
and "false" modes in sessionManager._get_ssl_context() don't use cert.py.
"""

import asyncio
import socket
import ssl
import struct
import threading
import warnings

import aiohttp
import httpx
import pytest

import ofscraper.__main__  # noqa: F401  resolves the settings/console import cycle
from ofscraper.managers.sessionmanager.cert import create_custom_ssl_context

# OP_NO_SSLv3 | OP_NO_TLSv1 | OP_NO_TLSv1_1 as raw bits; the named constants
# are deprecated
OLD_PROTOCOL_BITS = 0x02000000 | 0x04000000 | 0x10000000
HOST = "localhost"
# Listen on whatever localhost resolves to first (often ::1), so clients don't
# wait for a refused address before falling back.
_FAMILY, *_, _SOCKADDR = socket.getaddrinfo(HOST, None, type=socket.SOCK_STREAM)[0]
LOOPBACK = _SOCKADDR[0]


def _raw(ctx, port):
    sock = socket.create_connection((HOST, port))
    ctx.wrap_socket(sock, server_hostname=HOST).do_handshake()


# trust_env=False: a proxy set in the environment (HTTPS_PROXY etc.) would
# otherwise carry the localhost capture away from the test server.
def _httpx(ctx, port):
    with httpx.Client(http2=True, verify=ctx, trust_env=False) as client:
        client.get(f"https://{HOST}:{port}/")


def _aiohttp(ctx, port):
    async def go():
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ctx), trust_env=False
        ) as s:
            async with s.get(f"https://{HOST}:{port}/"):
                pass

    asyncio.run(go())


TRANSPORTS = {"raw": _raw, "httpx": _httpx, "aiohttp": _aiohttp}


def _client_hello(ctx, transport):
    srv = socket.socket(_FAMILY)
    srv.bind((LOOPBACK, 0))
    srv.listen(4)
    out = {}

    def accept():
        conn, _ = srv.accept()
        data = b""
        while len(data) < 5 or len(data) < 5 + struct.unpack(">H", data[3:5])[0]:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        out["hello"] = data
        conn.close()

    t = threading.Thread(target=accept)
    t.start()
    try:
        TRANSPORTS[transport](ctx, srv.getsockname()[1])
    except Exception:
        pass  # the fake server hangs up after the ClientHello
    t.join(timeout=10)
    srv.close()
    return out["hello"]


def _key_shares(data):
    # client key_share: list length, then (group, key length, key) entries.
    # Keep groups and lengths; the key bytes are random per connection.
    shares, p = [], 2
    while p + 4 <= len(data):
        group, length = struct.unpack(">HH", data[p : p + 4])
        shares.append((group, length))
        p += 4 + length
    return shares


def _fingerprint(hello):
    """Everything a TLS fingerprint can see, minus per-connection random bytes."""
    p = 5 + 4 + 2 + 32
    session_id_len = hello[p]
    p += 1 + session_id_len
    n = struct.unpack(">H", hello[p : p + 2])[0]
    ciphers = hello[p + 2 : p + 2 + n]
    p += 2 + n
    p += 1 + hello[p]
    end = p + 2 + struct.unpack(">H", hello[p : p + 2])[0]
    p += 2
    exts, order = {}, []
    while p < end:
        t, length = struct.unpack(">HH", hello[p : p + 4])
        order.append(t)
        exts[t] = hello[p + 4 : p + 4 + length]
        p += 4 + length
    if 51 in exts:
        exts[51] = _key_shares(exts[51])
    return {
        "session_id_len": session_id_len,
        "ciphers": ciphers,
        "extension_order": order,
        "extensions": exts,
        "length": len(hello),
    }


def _old_context():
    ctx = create_custom_ssl_context()
    with warnings.catch_warnings():
        # rebuilding the old option set on purpose
        warnings.simplefilter("ignore", DeprecationWarning)
        ctx.options = ssl.Options(int(ctx.options) | OLD_PROTOCOL_BITS)
    return ctx


def test_context_builds_without_deprecated_ssl_flags():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        ctx = create_custom_ssl_context()
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


@pytest.mark.parametrize("transport", TRANSPORTS)
def test_client_hello_matches_previous_options(transport):
    new = _fingerprint(_client_hello(create_custom_ssl_context(), transport))
    old = _fingerprint(_client_hello(_old_context(), transport))
    assert new == old
    assert new["extensions"].get(51), "key_share missing"


@pytest.mark.parametrize("transport", TRANSPORTS)
def test_client_hello_session_id_stays_empty(transport):
    # Python's default options would turn on middlebox compat and send a
    # 32-byte session ID, which changes the fingerprint (issue #110)
    hello = _client_hello(create_custom_ssl_context(), transport)
    assert _fingerprint(hello)["session_id_len"] == 0


def test_httpx_transport_offers_h2():
    # the raw socket sends no ALPN; httpx with http2=True offers h2 and http/1.1
    exts = _fingerprint(_client_hello(create_custom_ssl_context(), "httpx"))["extensions"]
    assert b"h2" in exts[16] and b"http/1.1" in exts[16]
