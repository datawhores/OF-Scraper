import getpass
import hashlib
import logging
import os
import random
import ssl
import sys
import time

import certifi

import ofscraper.utils.auth.request as auth_requests

log = logging.getLogger("shared")

# RAM Cache to track initialized configurations and suppress repeat logs
_CONFIG_CACHE = {}

def get_default_cipher_names():
    """
    Gets the default cipher names from a default SSL context.
    Returns a list of OpenSSL cipher names.
    """
    temp_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    return [c["name"] for c in temp_ctx.get_ciphers()]


def load_certifi_if_no_ca_certs(context: ssl.SSLContext) -> bool:
    """
    Loads certifi's CA bundle when the context has no system CA certificates,
    and returns whether it did.

    A python.org build on macOS has none until "Install Certificates.command"
    is run, so every HTTPS request fails certificate verification. The CA
    store isn't part of the ClientHello, so this leaves the TLS fingerprint
    alone.
    """
    if context.verify_mode == ssl.CERT_NONE:
        return False
    if context.cert_store_stats()["x509_ca"]:
        return False
    # certificates in a CA directory load on demand and aren't counted above
    capath = ssl.get_default_verify_paths().capath
    try:
        if capath and os.listdir(capath):
            return False
    except OSError:
        pass
    context.load_verify_locations(cafile=certifi.where())
    return True


_WINDOWS = sys.platform == "win32"


# The certificates load_system_ca_certs gives every context on Windows, as
# concatenated DER, with the time they were collected. A context is built for
# each request on the aiohttp path, so the store is read once and kept.
_windows_ca_cache = None
# an entry can expire while a daemon runs
_WINDOWS_CA_TTL = 24 * 60 * 60


def _windows_ca_certs() -> bytes:
    """
    The Windows store's CA certificates without the expired ones, plus
    certifi's bundle, as concatenated DER.

    Adding certifi means trusting Mozilla's roots as well as Windows': a root
    removed or distrusted in Windows is trusted again when certifi has it.
    """
    global _windows_ca_cache
    now = time.time()
    if _windows_ca_cache and now - _windows_ca_cache[0] < _WINDOWS_CA_TTL:
        return _windows_ca_cache[1]
    store = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    store.load_default_certs(ssl.Purpose.SERVER_AUTH)
    certs = {}
    # both calls list the store in the same order
    for der, info in zip(store.get_ca_certs(binary_form=True), store.get_ca_certs()):
        try:
            if ssl.cert_time_to_seconds(info["notAfter"]) <= now:
                continue
        except (KeyError, ValueError):
            pass
        certs[der] = None
    bundle = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    bundle.load_verify_locations(cafile=certifi.where())
    # a certificate in both is kept once
    certs.update(dict.fromkeys(bundle.get_ca_certs(binary_form=True)))
    _windows_ca_cache = (now, b"".join(certs))
    return _windows_ca_cache[1]


def load_system_ca_certs(context: ssl.SSLContext) -> None:
    """
    Loads the system's CA certificates, as load_default_certs does, but on
    Windows leaves out the expired ones and adds certifi's bundle.

    Python loads the whole Windows store, expired certificates included, and
    OpenSSL prefers a stored issuer to the one the server sends. An expired
    intermediate left in the store then fails a valid chain with "certificate
    has expired". Windows also fetches root certificates on demand, so a root
    can be missing from the store until something else has used it.
    """
    if not _WINDOWS:
        context.load_default_certs(ssl.Purpose.SERVER_AUTH)
        return
    context.load_verify_locations(cadata=_windows_ca_certs())


def _fansly_seed():
    """
    Seed for a Fansly profile, or None for OnlyFans (unchanged path).

    The OnlyFans auth reader prompts when auth.json is missing, so a Fansly
    profile must not reach it. The seed is a hash of the Fansly session id,
    read without prompting; the raw id is never used, since the seed's start
    is logged.
    """
    import ofscraper.sites as sites

    if not sites.is_fansly():
        return None
    from ofscraper.sites.fansly import auth as fansly_auth

    try:
        fauth = fansly_auth.read_auth()
    except Exception:
        fauth = {}
    sid = fansly_auth.session_id(fauth.get("authorization_token")) or fauth.get(
        "device_id"
    )
    if not sid:
        return "fansly_default_seed"
    return "fansly_" + hashlib.sha256(str(sid).encode()).hexdigest()[:16]


def create_custom_ssl_context(
    # --- Cipher Configuration ---
    cipher_suite_string: str = None,
    reorder_default_ciphers_enabled: bool = True,
    # --- TLS Version Configuration ---
    min_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
    max_tls_version: ssl.TLSVersion = None,
    # --- Elliptic Curve Configuration ---
    elliptic_curves_string: str = None,
    # --- Standard Security Options ---
    check_hostname: bool = True,
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED,
    load_default_ca_certs: bool = True,
    apply_common_opts: bool = True,
) -> ssl.SSLContext:
    """
    Creates and configures a custom SSLContext with User-ID stable hardening.
    Uses _CONFIG_CACHE to ensure logs are only printed once per unique user/profile.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # 1. Determine Identity for Logging Cache
    try:
        user_seed = _fansly_seed()
        if user_seed is None:
            auth = auth_requests.auth_file.read_auth()
            user_seed = str(auth.get("auth_id") or auth.get("username") or "default_seed")
    except Exception:
        user_seed = f"fallback_seed_{getpass.getuser()}"

    # Initialize cache entry for this identity if it doesn't exist
    if user_seed not in _CONFIG_CACHE:
        _CONFIG_CACHE[user_seed] = {"ciphers": None, "logged_tls": False, "logged_curves": False, "logged_certs": False}

    cache = _CONFIG_CACHE[user_seed]

    # --- TLS Version Configuration ---
    context.minimum_version = min_tls_version
    if max_tls_version:
        context.maximum_version = max_tls_version

    # --- Apply Common Security Options ---
    if apply_common_opts:
        # Old protocol versions are excluded by minimum_version; the OP_NO_SSL*/
        # OP_NO_TLS* flags are deprecated and changed nothing on the wire.
        # Keep assigning (not |=): it clears Python's default options such as
        # OP_ENABLE_MIDDLEBOX_COMPAT, so the ClientHello session ID stays empty.
        # Changing that changes the TLS fingerprint.
        options = ssl.Options(0)
        if hasattr(ssl, "OP_NO_COMPRESSION"):
            options |= ssl.OP_NO_COMPRESSION
        context.options = options

    # --- Configure Ciphers ---
    effective_cipher_string = cipher_suite_string

    if not effective_cipher_string and reorder_default_ciphers_enabled:
        if cache["ciphers"]:
            effective_cipher_string = cache["ciphers"]
        else:
            seed_int = int(hashlib.sha256(user_seed.encode()).hexdigest(), 16)
            rng = random.Random(seed_int)
            default_ciphers = get_default_cipher_names()

            if len(default_ciphers) >= 2:
                shuffled_ciphers = list(default_ciphers)
                rng.shuffle(shuffled_ciphers)
                effective_cipher_string = ":".join(shuffled_ciphers)
                cache["ciphers"] = effective_cipher_string
                # not the seed: it is the auth_id, username or OS user name
                log.debug("Harden: Generated stable TLS fingerprint")
            else:
                log.debug("Warning: Could not reorder default ciphers (list too short).")

    if effective_cipher_string:
        try:
            context.set_ciphers(effective_cipher_string)
        except ssl.SSLError as e:
            log.debug(f"Warning: Could not set ciphers: {e}.")
    elif not reorder_default_ciphers_enabled and not cache["logged_tls"]:
        log.debug("Info: Using OpenSSL default ciphers (Hardening Disabled).")
        cache["logged_tls"] = True

    # --- Configure Elliptic Curves ---
    if elliptic_curves_string:
        try:
            context.set_ecdh_curve(elliptic_curves_string)
        except (AttributeError, ssl.SSLError) as e:
            if not cache["logged_curves"]:
                log.debug(f"Warning: Could not set custom elliptic curves: {e}")
                cache["logged_curves"] = True

    # --- Standard Verification Settings ---
    context.check_hostname = check_hostname
    context.verify_mode = verify_mode
    if load_default_ca_certs:
        try:
            load_system_ca_certs(context)
        except Exception as e:
            if not cache["logged_certs"]:
                log.debug(f"Warning: Could not load default CAcerts: {e}.")
                cache["logged_certs"] = True
        if load_certifi_if_no_ca_certs(context) and not cache["logged_certs"]:
            log.debug("No system CA certificates found, using certifi's")
            cache["logged_certs"] = True

    return context