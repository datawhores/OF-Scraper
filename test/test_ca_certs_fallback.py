"""
A Python with no system CA certificates (a python.org build on macOS before
"Install Certificates.command" is run) failed every HTTPS request with
"certificate verify failed: unable to get local issuer certificate".

1. The SSL contexts fall back to certifi's CA bundle when the system has none.

On Windows, Python loads every certificate in the system store, expired ones
included, and OpenSSL prefers a stored issuer to the one the server sends. An
expired intermediate left in the store failed onlyfans.com with "certificate
has expired".

2. On Windows the custom context skips expired store certificates and adds
   certifi's bundle.
"""

import ssl
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  resolves the settings/console import cycle
import ofscraper.managers.sessionmanager.cert as cert
import ofscraper.managers.sessionmanager.sessionmanager as sessionmanager
import ofscraper.utils.settings as settings


@pytest.fixture
def no_system_certs(monkeypatch, tmp_path):
    cafile = tmp_path / "cert.pem"
    cafile.write_text("")
    capath = tmp_path / "certs"
    capath.mkdir()
    monkeypatch.setenv("SSL_CERT_FILE", str(cafile))
    monkeypatch.setenv("SSL_CERT_DIR", str(capath))
    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", _verify_paths_only)
    monkeypatch.setattr(
        cert.auth_requests.auth_file, "read_auth", lambda: {"auth_id": "11111"}
    )
    monkeypatch.setattr(cert, "_CONFIG_CACHE", {})
    monkeypatch.setattr(cert, "_windows_ca_cache", None)
    return capath


def _verify_paths_only(self, purpose=ssl.Purpose.SERVER_AUTH):
    # what load_default_certs does off Windows; on Windows it also reads the
    # system store, which the environment variables above don't empty
    self.set_default_verify_paths()


def _session_context(monkeypatch, ssl_verify):
    monkeypatch.setattr(
        settings, "get_settings", lambda: SimpleNamespace(ssl_verify=ssl_verify)
    )
    return sessionmanager.sessionManager._get_ssl_context(None)


@pytest.mark.parametrize("ssl_verify", ["custom", "default"])
def test_falls_back_to_certifi_without_system_certs(
    monkeypatch, no_system_certs, ssl_verify
):
    context = _session_context(monkeypatch, ssl_verify)
    assert context.cert_store_stats()["x509_ca"] > 0


def test_system_certs_are_used_alone_when_present(monkeypatch, no_system_certs):
    # a CA directory's certificates load on demand and aren't in the stats
    (no_system_certs / "0a1b2c3d.0").write_text("")
    context = _session_context(monkeypatch, "custom")
    assert context.cert_store_stats()["x509_ca"] == 0


def test_no_fallback_when_verification_is_off(no_system_certs):
    context = cert.create_custom_ssl_context(
        check_hostname=False, verify_mode=ssl.CERT_NONE
    )
    assert context.cert_store_stats()["x509_ca"] == 0


# A test root (valid until 2126) and an intermediate it signed that expired in
# 2021. Certificates only: no private key is kept.
ROOT = """\
-----BEGIN CERTIFICATE-----
MIIBbzCCARSgAwIBAgIUVVj/zwdRxu6+4qs50/wASFE8PyowCgYIKoZIzj0EAwIw
FDESMBAGA1UEAwwJVGVzdCBSb290MCAXDTI2MTExNjAzNDUyNVoYDzIxMjYxMDIz
MDM0NTI1WjAUMRIwEAYDVQQDDAlUZXN0IFJvb3QwWTATBgcqhkjOPQIBBggqhkjO
PQMBBwNCAASkbbT9H1gzT07QnzaJhua6o3XbDOXOI91fO1790odS1n8E9cBsEWLZ
n9URqJIml5Vq2yvAdeNlozYrGeLHaeXEo0IwQDAPBgNVHRMBAf8EBTADAQH/MA4G
A1UdDwEB/wQEAwIBBjAdBgNVHQ4EFgQUUNXsk4w6c/ABYMpNWuYSIHebpQAwCgYI
KoZIzj0EAwIDSQAwRgIhAKMK7gwPz54N67NOvsKMfMsOaV5gM8yzxmyUtRrf+cew
AiEAkJVFQi/JYvkVTJqpGs3bG5D9gZKa+2Inn63FojgUWtw=
-----END CERTIFICATE-----
"""
EXPIRED_INTERMEDIATE = """\
-----BEGIN CERTIFICATE-----
MIIBgjCCASigAwIBAgIBEDAKBggqhkjOPQQDAjAUMRIwEAYDVQQDDAlUZXN0IFJv
b3QwHhcNMjAwMTAxMDAwMDAwWhcNMjEwMTAxMDAwMDAwWjAcMRowGAYDVQQDDBFU
ZXN0IEludGVybWVkaWF0ZTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABNNyddzr
XJhfswTaluvSsUk/1CKmyeqIhAwHm2cnq51jJFXMRX8IXNdup2vBTPsxtw1s4k5d
Vr5wtcRL0+Q5to+jYzBhMA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEG
MB0GA1UdDgQWBBQzt4+P0vAY4mmUiyp66dHi6ffaQjAfBgNVHSMEGDAWgBRQ1eyT
jDpz8AFgyk1a5hIgd5ulADAKBggqhkjOPQQDAgNIADBFAiEAyPMUKpAurFbLdqCf
4E7qDoM3jtHM0oXLU8iq7UwEL0kCIBylqFKvmjJyjkYQTSrvMAkYHc36qEjKVsbR
x4uSLXcC
-----END CERTIFICATE-----
"""


@pytest.fixture
def store_with_expired_cert(monkeypatch, no_system_certs, tmp_path):
    cafile = tmp_path / "store.pem"
    cafile.write_text(ROOT + EXPIRED_INTERMEDIATE)
    monkeypatch.setenv("SSL_CERT_FILE", str(cafile))
    # certifi's bundle would hide the counts
    empty = tmp_path / "empty.pem"
    empty.write_text(ROOT)
    monkeypatch.setattr(cert.certifi, "where", lambda: str(empty))


def _subjects(context):
    return sorted(c["subject"][0][0][1] for c in context.get_ca_certs())


def test_windows_skips_expired_store_certs(monkeypatch, store_with_expired_cert):
    monkeypatch.setattr(cert, "_WINDOWS", True)
    context = cert.create_custom_ssl_context()
    assert _subjects(context) == ["Test Root"]


def test_windows_adds_certifi(monkeypatch, no_system_certs, tmp_path):
    monkeypatch.setattr(cert, "_WINDOWS", True)
    bundle = tmp_path / "bundle.pem"
    bundle.write_text(ROOT)
    monkeypatch.setattr(cert.certifi, "where", lambda: str(bundle))
    # the system store is empty here, so the root can only come from certifi;
    # the fallback for an empty store is off, to leave only the Windows path
    monkeypatch.setattr(cert, "load_certifi_if_no_ca_certs", lambda context: False)
    context = cert.create_custom_ssl_context()
    assert _subjects(context) == ["Test Root"]


@pytest.fixture
def store_reads(monkeypatch):
    """Counts reads of the system store."""
    reads = []
    load = ssl.SSLContext.load_default_certs

    def counted(self, purpose=ssl.Purpose.SERVER_AUTH):
        reads.append(1)
        load(self, purpose)

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", counted)
    return reads


def test_windows_reads_the_store_once_for_many_contexts(
    monkeypatch, store_with_expired_cert, store_reads
):
    # the aiohttp path builds a context for every request
    monkeypatch.setattr(cert, "_WINDOWS", True)
    # the first context reads the store, and once more to list the ciphers
    cert.create_custom_ssl_context()
    store_reads.clear()
    contexts = [cert.create_custom_ssl_context() for _ in range(5)]
    assert store_reads == []
    assert [_subjects(context) for context in contexts] == [["Test Root"]] * 5


def test_windows_reads_the_store_again_when_the_list_is_old(
    monkeypatch, store_with_expired_cert, store_reads
):
    monkeypatch.setattr(cert, "_WINDOWS", True)
    monkeypatch.setattr(cert, "_WINDOWS_CA_TTL", 0)
    cert.create_custom_ssl_context()
    store_reads.clear()
    cert.create_custom_ssl_context()
    cert.create_custom_ssl_context()
    assert len(store_reads) == 2


def test_other_systems_load_the_store_unchanged(monkeypatch, store_with_expired_cert):
    monkeypatch.setattr(cert, "_WINDOWS", False)
    context = cert.create_custom_ssl_context()
    assert _subjects(context) == ["Test Intermediate", "Test Root"]
