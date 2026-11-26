import re
import ofscraper.utils.paths.common as paths
from typing import Any

# The other cookies the app sends, hidden by name like the auth cookies: the
# CloudFront cookies of a signed stream (OnlyFans and Fansly), and the ones
# OnlyFans sets, which the session's cookie jar keeps and sends back.
_OTHER_COOKIES = r"fp|st|csrf|auth_hash|CloudFront-(?:Policy|Signature|Key-Pair-Id)"
# Fansly's ID headers. Only the token is registered by value.
_FANSLY_IDS = r"fansly-client-id|fansly-session-id"

# --- Default Patterns (Regex or Plain Text) ---
_DEFAULT_PATTERNS = {
    # Redacts API keys and session tokens (Fixed to stop at whitespace).
    # First in the query too: a DRM link gets them as separate params, so its
    # query starts with ?Policy=
    r"([?&])Policy=[^&\"'\s]+": r"\g<1>Policy={hidden}",
    r"([?&])Signature=[^&\"'\s]+": r"\g<1>Signature={hidden}",
    r"([?&])Key-Pair-Id=[^&\"'\s]+": r"\g<1>Key-Pair-Id={hidden}",
    # The login in a link, as OFSC_PROXY has it: http://user:password@host.
    # Ends at the last "@" before the host, so a raw "@" in the password is
    # hidden too. Stops at "/", so an "@" in a link's path is left alone.
    r"""(\b[a-zA-Z][\w+.-]*://)[^\s/'"<>]+@""": r"\g<1>{hidden}@",
    # Redacts common sensitive info
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b": "{ip_address}",  # IP Addresses
    # Auth values by name, whatever the value. Masking by value covers only
    # what auth.json holds: OnlyFans can send a new session cookie in a
    # set-cookie, and a failed request logs its headers, IDs included. The
    # auth_uid_<user id> and auth_uniq_<user id> cookies have the ID in their
    # name, so that goes too.
    # Cookie form: sess=...; auth_id=...; auth_uid_123=... The value may be
    # quoted, as a SimpleCookie repr shows it: <SimpleCookie: sess='...'>
    r"""(?i)\b(sess)=(['"]?)[^;\s'",]+\2""": r"\g<1>=\g<2>{sess}\g<2>",
    r"""(?i)\b(auth_id)=(['"]?)[^;\s'",]+\2""": r"\g<1>=\g<2>{hidden}\g<2>",
    r"""(?i)\b(auth_uid|auth_uniq)\w*=(['"]?)[^;\s'",]+\2""": r"\g<1>=\g<2>{hidden}\g<2>",
    # Header, dict or JSON form: 'sess': '...', "x-bc": "...", 'auth_id': 123
    r"""(?i)(['"])(sess)\1(\s*:\s*)(['"])[^'"]+\4""": r"\g<1>\g<2>\g<1>\g<3>\g<4>{sess}\g<4>",
    r"""(?i)(['"])(x-bc)\1(\s*:\s*)(['"])[^'"]+\4""": r"\g<1>\g<2>\g<1>\g<3>\g<4>{x-bc}\g<4>",
    r"""(?i)(['"])(user-id|auth_id|auth_uid|auth_uniq)\w*\1(\s*:\s*)(['"]?)[^'",}\s]+\4""": r"\g<1>\g<2>\g<1>\g<3>\g<4>{hidden}\g<4>",
    # The other cookies, in both forms: fp=...; 'st': '...'
    rf"""(?i)\b({_OTHER_COOKIES})=(['"]?)[^;\s'",]+\2""": r"\g<1>=\g<2>{hidden}\g<2>",
    rf"""(?i)(['"])({_OTHER_COOKIES})\1(\s*:\s*)(['"])[^'"]+\4""": r"\g<1>\g<2>\g<1>\g<3>\g<4>{hidden}\g<4>",
    # Header line or query form: x-bc: ..., x-bc=..., user-id: 123. A user ID
    # is a number, so prose such as "the user-id: header" is left alone.
    r"(?i)\b(x-bc)(\s*[:=]\s*)(?!['\"])[^\s'\",;&]+": r"\g<1>\g<2>{x-bc}",
    r"(?i)\b(user-id)(\s*[:=]\s*)\d+": r"\g<1>\g<2>{hidden}",
    # Fansly's device and session IDs, in the same forms as x-bc:
    # 'fansly-client-id': '...', "fansly-session-id": 123, fansly-client-id: ...
    rf"""(?i)(['"])({_FANSLY_IDS})\1(\s*:\s*)(['"]?)[^'",}}\s]+\4""": r"\g<1>\g<2>\g<1>\g<3>\g<4>{hidden}\g<4>",
    rf"(?i)\b({_FANSLY_IDS})(\s*[:=]\s*)(?!['\"])[^\s'\",;&]+": r"\g<1>\g<2>{hidden}",
    # The request-signing header, as a header dict or JSON shows it
    # ('sign': '...'). It changes on every request, so it can't be
    # registered by value the way the session cookie is.
    r"(['\"](?i:sign)['\"]\s*:\s*['\"])[^'\"]+": r"\g<1>{sign}",
}

# This dictionary will be populated at runtime by your add_sensitive_pattern function
_USER_ADDED_PATTERNS = {}

# A link inside other text, up to a space, quote or bracket: aiohttp's error
# text writes url='...' or url=URL('...')
_LINK = re.compile(r"\bhttps?://[^\s'\"<>()]+")


def hide_link(url: Any, hide_path: bool = False) -> str:
    """
    A link as a log line shows it, with its query (a signed link's Policy,
    Signature and Key-Pair-Id, the account's user id) as {hidden}. hide_path
    also hides the path's longer names, which name the file, as get_url_log
    does for a media link. Only for logging: the link sent is unchanged.
    """
    link, _, query = str(url).partition("?")
    if hide_path:
        site = re.match(r"[\w+.-]+://[^/]*", link)
        start = site.end() if site else 0
        link = link[:start] + re.sub(r"/\w{5}\w+", "/{hidden}", link[start:])
    return f"{link}?{{hidden}}" if query else link


def hide_links(text: Any, hide_path: bool = False) -> str:
    """Text (an error, a traceback) with every link in it as hide_link shows it."""
    return _LINK.sub(lambda m: hide_link(m.group(0), hide_path), str(text))


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
        # Only as a whole name: a home folder called "dan" must not turn
        # "danger" into "{home_directory}ger". "_" isn't counted as part of
        # the name, so it is still hidden in a file name like "dan_log.txt".
        # In a path (after / or \) it is hidden whatever its case: the home
        # folder can be "Dan" or "DAN" when the account is "dan". Elsewhere
        # only the exact name is, so "Dan" in a sentence is left alone.
        name = re.escape(str(profile_dir))
        combined_patterns.setdefault(
            rf"(?:(?<=[\\/])(?i:{name})|(?<![^\W_]){name})(?![^\W_])",
            "{home_directory}",
        )

    return combined_patterns
