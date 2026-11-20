"""
unavailable_message only knew httpx errors. The async session (the GUI's
model list) raises aiohttp errors, so a network failure there was treated
as a problem with the auth.
"""

import asyncio
import json
import ssl

import aiohttp
import httpx
import pytest
from aiohttp.client_reqrep import ConnectionKey, RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

import ofscraper.__main__  # noqa: F401  resolves the settings/console import cycle
from ofscraper.data.api.init import unavailable_message

HOST = "onlyfans.com"
URL_ = f"https://{HOST}/api2/v2/subscriptions/subscribes"


def _conn_key():
    return ConnectionKey(
        host=HOST,
        port=443,
        is_ssl=True,
        ssl=True,
        proxy=None,
        proxy_auth=None,
        proxy_headers_hash=None,
    )


def _response_error(status):
    info = RequestInfo(URL(URL_), "GET", CIMultiDictProxy(CIMultiDict()))
    return aiohttp.ClientResponseError(info, (), status=status, message="x")


def test_connector_error_names_the_host_and_cause():
    e = aiohttp.ClientConnectorError(_conn_key(), OSError(11001, "getaddrinfo failed"))
    message = unavailable_message(e)
    assert message.startswith(
        f"Couldn't reach {HOST} (connection failed). Check your connection or VPN. "
        "Error: "
    )
    assert "getaddrinfo failed" in message


def test_server_disconnected_is_a_connection_failure():
    assert unavailable_message(aiohttp.ServerDisconnectedError()) == (
        "Couldn't reach the server (connection failed). "
        "Check your connection or VPN. Error: Server disconnected"
    )


@pytest.mark.parametrize(
    "error",
    [
        aiohttp.ServerTimeoutError("Timeout on reading data from socket"),
        aiohttp.ConnectionTimeoutError("Connection timeout to host"),
        aiohttp.SocketTimeoutError("Timeout on reading data from socket"),
    ],
)
def test_timeouts_say_timed_out(error):
    assert unavailable_message(error) == (
        "Couldn't reach the server (timed out). Check your connection or VPN."
    )


def test_certificate_error_gets_the_certificate_message():
    cause = ssl.SSLCertVerificationError(
        1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
    )
    cause.verify_message = "unable to get local issuer certificate"
    e = aiohttp.ClientConnectorCertificateError(_conn_key(), cause)
    assert unavailable_message(e) == (
        f"Couldn't verify the certificate of {HOST} "
        "(unable to get local issuer certificate). A proxy, VPN or antivirus may "
        "be intercepting HTTPS, or this Python has no CA certificates."
    )


def test_other_ssl_error_is_a_connection_failure():
    e = aiohttp.ClientConnectorSSLError(
        _conn_key(), ssl.SSLError(1, "[SSL: WRONG_VERSION_NUMBER] wrong version number")
    )
    message = unavailable_message(e)
    assert message.startswith(f"Couldn't reach {HOST} (connection failed).")
    assert "WRONG_VERSION_NUMBER" in message


def test_rate_limit():
    assert unavailable_message(_response_error(429)) == (
        f"{HOST} is rate limiting requests. Try again later."
    )


@pytest.mark.parametrize("status", [500, 503])
def test_server_error(status):
    assert unavailable_message(_response_error(status)) == (
        f"{HOST} returned {status}: the server had an error. Try again later."
    )


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_left_to_the_auth_check(status):
    assert unavailable_message(_response_error(status)) is None


# real aiohttp requests against a local server, so each error is the one
# aiohttp actually raises


async def _serve(reply, run):
    """Run run(port) against a local server that answers each request with reply."""

    async def handle(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
            if reply is None:
                # never answer
                await reader.read()
            else:
                writer.write(reply)
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        async with server:
            return await run(port)
    finally:
        server.close()
        await server.wait_closed()


def _raised(reply, request):
    async def run(port):
        async with aiohttp.ClientSession() as session:
            try:
                await request(session, port)
            except Exception as e:
                return e
        raise AssertionError("no error")

    return asyncio.run(_serve(reply, run))


def _through_proxy(status_line):
    async def request(session, port):
        async with session.get(URL_, proxy=f"http://127.0.0.1:{port}"):
            pass

    return _raised(
        f"HTTP/1.1 {status_line}\r\nContent-Length: 0\r\n\r\n".encode(), request
    )


async def _read(session, port, timeout=None):
    async with session.get(f"http://127.0.0.1:{port}/", timeout=timeout) as r:
        await r.read()


async def _json(session, port):
    async with session.get(f"http://127.0.0.1:{port}/") as r:
        await r.json()


@pytest.mark.parametrize(
    "status_line",
    ["407 Proxy Authentication Required", "502 Bad Gateway"],
)
def test_proxy_refusal_is_a_connection_failure(status_line):
    e = _through_proxy(status_line)
    assert isinstance(e, aiohttp.ClientHttpProxyError)
    assert unavailable_message(e) == (
        f"Couldn't reach {HOST} through the proxy (connection failed). "
        f"Check your proxy settings. Error: the proxy answered {status_line}"
    )


def test_html_reply_is_not_json():
    e = _raised(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 6\r\n\r\n"
        b"<html>",
        _json,
    )
    assert isinstance(e, aiohttp.ContentTypeError)
    assert unavailable_message(e) == unavailable_message(
        json.JSONDecodeError("Expecting value", "<html>", 0)
    )
    assert unavailable_message(e).startswith("Got a reply that isn't JSON")


@pytest.mark.parametrize("status", [401, 403])
def test_html_client_error_is_left_to_the_auth_check(status):
    info = RequestInfo(URL(URL_), "GET", CIMultiDictProxy(CIMultiDict()))
    e = aiohttp.ContentTypeError(info, (), status=status, message="x")
    assert unavailable_message(e) is None


def test_cut_off_body_is_a_connection_failure():
    e = _raised(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Content-Length: 100\r\n\r\n{",
        _read,
    )
    assert isinstance(e, aiohttp.ClientPayloadError)
    assert unavailable_message(e).startswith(
        "Couldn't reach the server (connection failed). "
        "Check your connection or VPN. Error: Response payload is not completed"
    )


def test_total_timeout_says_timed_out():
    async def request(session, port):
        await _read(session, port, aiohttp.ClientTimeout(total=0.2, sock_read=None))

    e = _raised(None, request)
    # aiohttp raises a bare TimeoutError here, not one of its own errors
    assert type(e) is TimeoutError
    assert unavailable_message(e) == (
        "Couldn't reach the server (timed out). Check your connection or VPN."
    )


def test_other_timeouts_are_not_network_errors():
    async def wait():
        await asyncio.wait_for(asyncio.Event().wait(), 0.01)

    with pytest.raises(TimeoutError) as caught:
        asyncio.run(wait())
    assert unavailable_message(caught.value) is None
    assert unavailable_message(TimeoutError("Subprocess timed out")) is None


# the httpx messages are unchanged


def _httpx_status_error(status):
    request = httpx.Request("GET", URL_)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("x", request=request, response=response)


def test_httpx_messages_unchanged():
    request = httpx.Request("GET", URL_)
    assert unavailable_message(httpx.ReadTimeout("", request=request)) == (
        f"Couldn't reach {HOST} (timed out). Check your connection or VPN."
    )
    assert unavailable_message(_httpx_status_error(429)) == (
        f"{HOST} is rate limiting requests. Try again later."
    )
    assert unavailable_message(_httpx_status_error(503)) == (
        f"{HOST} returned 503: the server had an error. Try again later."
    )
    assert unavailable_message(_httpx_status_error(401)) is None
    assert unavailable_message(ValueError("x")) is None
