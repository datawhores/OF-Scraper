"""
Pin the TLS ClientHello that create_custom_ssl_context() produces.

The ClientHello is captured through each transport that uses the context: a
raw socket, httpx (sync, HTTP/2) and aiohttp (async). Transports differ, e.g.
httpx adds ALPN. This covers the "custom" ssl_verify mode only; the "default"
and "false" modes in sessionManager._get_ssl_context() don't use cert.py.
"""

import asyncio
import select
import socket
import ssl
import struct
import threading
import warnings

import aiohttp
import httpx
import pytest
from aiohttp.resolver import DefaultResolver

import ofscraper.__main__  # noqa: F401  resolves the settings/console import cycle
from ofscraper.managers.sessionmanager.addresses import Resolver
from ofscraper.managers.sessionmanager.cert import create_custom_ssl_context

# OP_NO_SSLv3 | OP_NO_TLSv1 | OP_NO_TLSv1_1 as raw bits; the named constants
# are deprecated
OLD_PROTOCOL_BITS = 0x02000000 | 0x04000000 | 0x10000000
HOST = "localhost"
# Listen on every address localhost resolves to. Clients don't agree on which
# one to use: aiohttp resolves with AI_ADDRCONFIG, which leaves out ::1 on a
# machine with no IPv6 network address, while a plain lookup lists ::1 first.
LOOPBACKS = list(
    dict.fromkeys(
        (info[0], info[4][0])
        for info in socket.getaddrinfo(HOST, None, type=socket.SOCK_STREAM)
    )
)


def _listen_once():
    """One listener per loopback address, all on the port the first got."""
    servers, port = [], 0
    try:
        for family, address in LOOPBACKS:
            srv = socket.socket(family)
            servers.append(srv)
            srv.bind((address, port))
            srv.listen(4)
            port = srv.getsockname()[1]
    except OSError:
        for srv in servers:
            srv.close()
        raise
    return servers


def _listeners(attempts=20):
    # the port free on the first address can be taken on another one; pick
    # a new port and try again
    for attempt in range(attempts):
        try:
            return _listen_once()
        except OSError:
            if attempt == attempts - 1:
                raise


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


def _session_connector(ctx, port):
    """aiohttp with its connector set up as the session manager's: the
    resolver keeps the addresses (#622)."""

    async def go():
        resolver = Resolver(DefaultResolver())
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    ssl=ctx, resolver=resolver, use_dns_cache=False
                ),
                trust_env=False,
            ) as s:
                async with s.get(f"https://{HOST}:{port}/"):
                    pass
        finally:
            await resolver.close()

    asyncio.run(go())


TRANSPORTS = {
    "raw": _raw,
    "httpx": _httpx,
    "aiohttp": _aiohttp,
    "session-connector": _session_connector,
}


def _client_hello(ctx, transport):
    servers = _listeners()
    out = {}

    def accept():
        ready, _, _ = select.select(servers, [], [], 10)
        if not ready:
            return
        conn, _ = ready[0].accept()
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
    error = None
    try:
        TRANSPORTS[transport](ctx, servers[0].getsockname()[1])
    except Exception as exc:
        error = exc  # expected: the fake server hangs up after the ClientHello
    t.join(timeout=15)
    for srv in servers:
        srv.close()
    assert "hello" in out, f"{transport} never reached the test server: {error!r}"
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


def test_the_session_connector_sends_what_plain_aiohttp_sends():
    # the connector only changes how a host is looked up (#622)
    ctx = create_custom_ssl_context()
    assert _fingerprint(_client_hello(ctx, "session-connector")) == _fingerprint(
        _client_hello(ctx, "aiohttp")
    )


def test_httpx_transport_offers_h2():
    # the raw socket sends no ALPN; httpx with http2=True offers h2 and http/1.1
    exts = _fingerprint(_client_hello(create_custom_ssl_context(), "httpx"))["extensions"]
    assert b"h2" in exts[16] and b"http/1.1" in exts[16]


def test_listeners_retry_when_the_port_is_taken_on_another_address(monkeypatch):
    real = _listen_once
    tries = []

    def listen_once():
        tries.append(1)
        if len(tries) < 3:
            raise OSError("address already in use")  # taken on the 2nd address
        return real()

    monkeypatch.setitem(globals(), "_listen_once", listen_once)
    servers = _listeners()
    try:
        assert len(tries) == 3
        assert len(servers) == len(LOOPBACKS)
        assert len({srv.getsockname()[1] for srv in servers}) == 1
    finally:
        for srv in servers:
            srv.close()


def test_a_failed_attempt_closes_what_it_opened(monkeypatch):
    opened = []
    real_socket = socket.socket

    class _Socket(real_socket):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            opened.append(self)

        def bind(self, addr):
            if len(opened) > 1:  # the second address: port taken
                raise OSError("address already in use")
            return super().bind(addr)

    monkeypatch.setitem(
        globals(), "LOOPBACKS", [(socket.AF_INET, "127.0.0.1")] * 2
    )
    monkeypatch.setattr(socket, "socket", _Socket)
    try:
        _listen_once()
    except OSError:
        pass
    else:
        raise AssertionError("the second bind should have failed")
    assert len(opened) == 2 and all(s.fileno() == -1 for s in opened)
