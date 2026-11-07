import re
import ofscraper.utils.paths.common as paths
from typing import Any

# --- Default Patterns (Regex or Plain Text) ---
_DEFAULT_PATTERNS = {
    # Redacts API keys and session tokens (Fixed to stop at whitespace)
    r"&Policy=[^&\"'\s]+": "&Policy={hidden}",
    r"&Signature=[^&\"'\s]+": "&Signature={hidden}",
    r"&Key-Pair-Id=[^&\"'\s]+": "&Key-Pair-Id={hidden}",
    # Redacts common sensitive info
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b": "{ip_address}",  # IP Addresses
    r"\"sess\":\"[^\"]+\"": '"sess":"{hidden}"',  # Session tokens
    # The request-signing header, as a header dict or JSON shows it
    # ('sign': '...'). It changes on every request, so it can't be
    # registered by value the way the session cookie is.
    r"(['\"](?i:sign)['\"]\s*:\s*['\"])[^'\"]+": r"\g<1>{sign}",
}

# This dictionary will be populated at runtime by your add_sensitive_pattern function
_USER_ADDED_PATTERNS = {}


def add_sensitive_pattern(pattern: Any, replacement: Any = "{hidden}"):
    """
    Dynamically adds a new pattern. It intelligently handles strings,
    numbers, and compiled regex objects to prevent errors.
    """
    key = ""
    # If the pattern is a compiled regex object (re.Pattern)
    if isinstance(pattern, re.Pattern):
        # Use its .pattern attribute to get the original string
        key = pattern.pattern
    else:
        # For anything else (numbers, strings), use str() as a safe fallback
        key = str(pattern)

    _USER_ADDED_PATTERNS[key] = str(replacement)


def getSenstiveDict() -> dict:
    """
    Returns a combined dictionary of default, user-added, and dynamic patterns.
    """
    # Dicts keep insertion order, which is the order they're applied in:
    # built-in rules, then patterns added during the session (exact values
    # such as the session cookie or user id), then the home folder name last.
    # The home folder name is short and could otherwise rewrite part of a
    # secret so it no longer matches.
    combined_patterns = _DEFAULT_PATTERNS.copy()
    combined_patterns.update(_USER_ADDED_PATTERNS)

    # --- Add Dynamic Patterns ---
    # These are generated based on the current user's specific info.

    # 2. Redact profile/download directory paths
    profile_dir = paths.get_username()
    if profile_dir:
        # Escape the path for regex and replace it
        combined_patterns.setdefault(re.escape(str(profile_dir)), "{home_directory}")

    return combined_patterns
