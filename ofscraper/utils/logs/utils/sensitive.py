import re
import ofscraper.utils.paths.common as paths
from typing import Any


# --- Default Patterns (Regex or Plain Text) ---
_DEFAULT_PATTERNS = {
    # Redacts API keys and session tokens
    r"&Policy=[^&\"']+": "&Policy={hidden}",
    r"&Signature=[^&\"']+": "&Signature={hidden}",
    r"&Key-Pair-Id=[^&\"']+": "&Key-Pair-Id={hidden}",
    # Redacts common sensitive info
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b": "{ip_address}",  # IP Addresses
    r"\"sess\":\"[^\"]+\"": '"sess":"{hidden}"',  # Session tokens
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
    combined_patterns = _DEFAULT_PATTERNS.copy()

    # --- Add Dynamic Patterns ---
    # These are generated based on the current user's specific info.

    # 2. Redact profile/download directory paths
    profile_dir = paths.get_username()
    if profile_dir:
        # Escape the path for regex and replace it
        combined_patterns[re.escape(str(profile_dir))] = "{home_directory}"

    # Add any patterns the user added manually during the session
    combined_patterns.update(_USER_ADDED_PATTERNS)

    return combined_patterns
