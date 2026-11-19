"""
The auth check reported every connection failure as "Couldn't reach <host>
(connection failed). Check your connection or VPN.", a certificate
verification failure included, and the cause was only in the debug log.
"""

import ssl

import httpx

import ofscraper.__main__  # noqa: F401  resolves the settings/console import cycle
from ofscraper.data.api.init import unavailable_message


def _connect_error(cause):
    request = httpx.Request("GET", "https://raw.githubusercontent.com/a/b.json")
    try:
        try:
            raise cause
        except Exception as inner:
            raise httpx.ConnectError(str(inner), request=request) from inner
    except httpx.ConnectError as e:
        return e


def test_certificate_failure_is_not_called_a_connection_failure():
    cause = ssl.SSLCertVerificationError(
        1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
    )
    cause.verify_message = "unable to get local issuer certificate"
    message = unavailable_message(_connect_error(cause))
    assert "certificate" in message
    assert "unable to get local issuer certificate" in message
    assert "raw.githubusercontent.com" in message
    assert "connection failed" not in message


def test_connect_error_message_carries_the_cause():
    message = unavailable_message(
        _connect_error(OSError("[Errno 11001] getaddrinfo failed"))
    )
    assert message == (
        "Couldn't reach raw.githubusercontent.com (connection failed). "
        "Check your connection or VPN. Error: [Errno 11001] getaddrinfo failed"
    )


def test_connect_error_without_text_has_no_empty_cause():
    request = httpx.Request("GET", "https://onlyfans.com/api2/v2/users/me")
    message = unavailable_message(httpx.ReadError("", request=request))
    assert message == (
        "Couldn't reach onlyfans.com (connection failed). "
        "Check your connection or VPN."
    )
