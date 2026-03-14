import ssl
import logging

log = logging.getLogger("shared")

def get_default_cipher_names():
    """
    Gets the default cipher names from a default SSL context.
    Returns a list of OpenSSL cipher names.
    """
    # Create a temporary default context to inspect its ciphers
    # This context reflects Python's recommended secure defaults.
    temp_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    default_ciphers_info = temp_ctx.get_ciphers()
    # Extract the OpenSSL cipher names
    return [c["name"] for c in default_ciphers_info]


def create_custom_ssl_context(
    # --- Cipher Configuration ---
    cipher_suite_string: str = None,
    reorder_default_ciphers_enabled: bool = True, 
    # Ignored if cipher_suite_string is provided.
    # --- TLS Version Configuration ---
    min_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
    max_tls_version: ssl.TLSVersion = None,  # None allows OpenSSL's default max for PROTOCOL_TLS_CLIENT
    # --- Elliptic Curve Configuration ---
    elliptic_curves_string: str = None,  # e.g., 'X25519:P-256:P-384'
    # --- Standard Security Options (generally keep these as True/CERT_REQUIRED) ---
    check_hostname: bool = True,
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED,
    load_default_ca_certs: bool = True,
    apply_common_opts: bool = True,  # Applies OP_NO_SSLv*, OP_NO_TLSv1*, OP_NO_COMPRESSION
) -> ssl.SSLContext:
    """
    Creates and configures a custom SSLContext with more abstracted modifications.

    If no cipher_suite_string is given and reorder_default_ciphers_enabled is False,
    the SSLContext will use OpenSSL's default ciphers.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Apply TLS versions
    context.minimum_version = min_tls_version
    if max_tls_version:
        context.maximum_version = max_tls_version

    # Apply common security options
    if apply_common_opts:
        options = (
            ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        )
        if hasattr(ssl, "OP_NO_COMPRESSION"):  # Python 3.3+
            options |= ssl.OP_NO_COMPRESSION
        context.options = options

    # --- Configure Ciphers ---
    # Start with the manual input (usually None)
    effective_cipher_string = cipher_suite_string

    if not effective_cipher_string and reorder_default_ciphers_enabled:
        default_ciphers = get_default_cipher_names()
        if len(default_ciphers) >= 2:
            swapped_ciphers = list(default_ciphers)  # Make a mutable copy
            swapped_ciphers[0], swapped_ciphers[1] = (
                swapped_ciphers[1],
                swapped_ciphers[0],
            )
            effective_cipher_string = ":".join(swapped_ciphers)
            log.debug(
                f"Harden: Reordered default ciphers. New order: {swapped_ciphers[0]}, {swapped_ciphers[1]}"
            )
        else:
            log.debug(
                "Warning: Could not reorder default ciphers (list too short)."
            )

    # FIX: Apply the cipher string if it was either provided or generated
    if effective_cipher_string:
        try:
            context.set_ciphers(effective_cipher_string)
        except ssl.SSLError as e:
            log.debug(
                f"Warning: Could not set ciphers '{effective_cipher_string}': {e}."
            )
    else:
        # hits only if reordering is disabled and no suite string provided
        log.debug(
            "Info: Using OpenSSL default ciphers for the configured TLS versions."
        )

    # --- Configure Elliptic Curves ---
    if elliptic_curves_string:
        try:
            context.set_ecdh_curve(elliptic_curves_string)
        except AttributeError:  
            log.debug(
                "Warning: set_ecdh_curve is not available on this Python/OpenSSL version."
            )
        except ssl.SSLError as e:
            log.debug(
                f"Warning: Could not set custom elliptic curves '{elliptic_curves_string}': {e}"
            )

    # --- Standard Verification Settings ---
    context.check_hostname = check_hostname
    context.verify_mode = verify_mode
    if load_default_ca_certs:
        try:
            context.load_default_certs(ssl.Purpose.SERVER_AUTH)
        except Exception as e:
            log.debug(f"Warning: Could not load default CAcerts: {e}.")

    return context