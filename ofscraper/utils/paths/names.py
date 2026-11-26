"""Single home for file and folder naming rules across platforms.

Each rule lives in one function here so callers (placeholder templates,
config checks, caption cleanup, livestream folders, and path truncation)
don't keep diverging copies (#856).

Note on ``pathvalidate``: evaluated against our pinned name tests and not
used here because ``pathvalidate`` differs in ways that would rename
existing downloads or weaken checks — it accepts ``"CON .txt"`` on Windows,
treats ``"COM0"``/``"LPT0"`` as reserved, leaves ``"."``/``".."`` alone,
strips trailing dots/spaces on Windows, strips DEL on POSIX, and counts
UTF-8 bytes rather than Windows UTF-16 whole-path units or macOS NFD
UTF-16 units.
"""

import logging
import ntpath
import os
import pathlib
import platform
import re
import unicodedata

import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")

# ----------------------------------------------------------------------
# 1. Characters a file or folder name cannot hold
# ----------------------------------------------------------------------

# Characters disallowed in a file or folder name on Windows (and slashes,
# which would introduce extra folders).
WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')

# Outside Windows a name can hold anything except "/" (a folder separator)
# and NUL, so a ":" from HH:mm in a date format stays.
POSIX_FORBIDDEN = re.compile(r"[/\x00]")

# Captions also drop ";" in addition to WINDOWS_FORBIDDEN.
CAPTION_FORBIDDEN = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*;]+')


def on_windows() -> bool:
    return platform.system() == "Windows"


def strip_forbidden(text, *, windows=None) -> str:
    """Remove characters a file name cannot hold on this system."""
    if windows is None:
        windows = on_windows()
    banned = WINDOWS_FORBIDDEN if windows else POSIX_FORBIDDEN
    return banned.sub("", str(text))


def has_forbidden(text: str) -> bool:
    """True when ``text`` contains any Windows-forbidden name character."""
    return bool(WINDOWS_FORBIDDEN.search(text))


def clean_label(label) -> str:
    """Make a label name safe as a folder or file name component."""
    return WINDOWS_FORBIDDEN.sub("", str(label)).strip() or "None"


def strip_caption_chars(text: str) -> str:
    """Remove characters disallowed in caption-derived file names."""
    return CAPTION_FORBIDDEN.sub("", text)


def clean_folder_name(cleaned_name: str, fallback: str = "unknown") -> str:
    """Finalize a single folder component by removing backslashes and
    leading/trailing spaces or dots."""
    name = str(cleaned_name).replace("\\", "").strip(" .")
    return name or fallback


# ----------------------------------------------------------------------
# 2. Reserved names and dots-only names
# ----------------------------------------------------------------------

# Names Windows reserves for devices, with or without an extension ("con.txt",
# "CON .txt").
WINDOWS_DEVICE = re.compile(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?=\s*(\.|$))")

# Names made solely of dots and spaces ("." / ".." / ". " / "...").
DOTS_ONLY = re.compile(r"\s*\.[.\s]*")


def is_dots_only(part: str) -> bool:
    """True when a path component consists solely of dots and whitespace."""
    return bool(DOTS_ONLY.fullmatch(part))


def escape_windows_device(part: str) -> str:
    """Append '_' to a Windows reserved device name (e.g. 'CON.txt' -> 'CON_.txt')."""
    return WINDOWS_DEVICE.sub(r"\1_", part)


def safe_parts(path, literal=None, *, windows=None) -> str:
    """Clean each component of ``path`` so no non-literal component is
    dots-only (replaced with '_') and, on Windows, no component is a reserved
    device name.

    ``literal`` marks each character written directly by the template itself:
    a component made solely of literal characters (such as ``dir_format "."``)
    is preserved.
    """
    path = str(path)
    literal = literal or [False] * len(path)
    if windows is None:
        windows = on_windows()
    out, start = [], 0
    for part in re.split(r"([/\\])", path):
        own = all(literal[start : start + len(part)])
        start += len(part)
        if len(out) % 2:
            pass
        elif is_dots_only(part) and not own:
            part = "_"
        elif windows:
            # only Windows has device names: elsewhere "aux" is a name
            part = escape_windows_device(part)
        out.append(part)
    return "".join(out)


# ----------------------------------------------------------------------
# 3. Length limits per system and shortening that keeps an ending
# ----------------------------------------------------------------------


def split_extension(name: str, keep_suffix: str = "") -> tuple[str, str]:
    """Return ``(stem, ext)`` where ``ext`` is ``keep_suffix`` if given, else
    a trailing extension (with an optional ``_1``-style counter before it) up
    to 10 alphanumeric characters long."""
    if keep_suffix:
        return name.removesuffix(keep_suffix), keep_suffix
    match = re.search(r"_[0-9]+\.[a-z0-9]{1,10}$", name, re.IGNORECASE) or re.search(
        r"\.[a-z0-9]{1,10}$", name, re.IGNORECASE
    )
    ext = match.group(0) if match else ""
    return (name[: -len(ext)] if ext else name), ext


def longest_fitting(text: str, size, max_size: int) -> str:
    """The longest prefix of ``text`` whose ``size`` is at most ``max_size``."""
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if size(text[:mid]) <= max_size:
            low = mid
        else:
            high = mid - 1
    return text[:low]


def windows_byte_size(text) -> int:
    """Size of ``text`` as Windows counts a path: 2 bytes per UTF-16 code unit
    (4 bytes for non-BMP characters such as emoji, 2 for all others)."""
    return len(str(text).encode("utf-16-le"))


def mac_name_size(text) -> int:
    """Size of a component under both macOS filesystems: APFS counts UTF-8
    bytes; HFS+ counts UTF-16 code units of the NFD decomposition. Returns the
    larger of the two so a name that fits works on either."""
    text = str(text)
    decomposed = unicodedata.normalize("NFD", text)
    return max(len(text.encode("utf-8")), len(decomposed.encode("utf-16-le")) // 2)


def unix_byte_size(text) -> int:
    """Estimated byte size of ``text`` on Linux/Unix using configured
    NORMAL_CHAR_SIZE_UNIX / SPECIAL_CHAR_SIZE_UNIX / UTF settings."""
    total_size = 0
    text = str(text)
    normal_char_size = of_env.getattr("NORMAL_CHAR_SIZE_UNIX")
    special_char_size = of_env.getattr("SPECIAL_CHAR_SIZE_UNIX")
    utf = of_env.getattr("UTF")

    if utf:
        return len(text.encode(utf))
    for char in text:
        try:
            if ord(char) < 128:
                total_size += normal_char_size
            else:
                total_size += special_char_size
        except ValueError:
            total_size += special_char_size
    return total_size


def truncate_windows(path, keep_suffix: str = "") -> pathlib.Path:
    """Shorten ``path``'s filename to fit ``WINDOWS_MAX_PATH_BYTES`` (whole path)."""
    path = pathlib.PureWindowsPath(ntpath.normpath(path))
    limit = of_env.getattr("WINDOWS_MAX_PATH_BYTES")
    if windows_byte_size(path) <= limit:
        return pathlib.Path(str(path))
    dir_part = path.parent
    file_part, ext = split_extension(path.name, keep_suffix)
    sep = "" if str(dir_part).endswith(ntpath.sep) else ntpath.sep
    max_bytes = (
        limit
        - windows_byte_size(dir_part)
        - windows_byte_size(sep)
        - windows_byte_size(ext)
    )
    name = longest_fitting(file_part, windows_byte_size, max_bytes)
    if not ext:
        # Windows drops trailing spaces and dots from a name
        name = name.rstrip(" .")
    if not name:
        raise ValueError(f"the folder is too long for any file name to fit: {path}")
    new_file = f"{name}{ext}"
    final_path = pathlib.PureWindowsPath(dir_part, new_file)
    log.debug(f"path: {path} filepath bytesize: {windows_byte_size(final_path)}")
    return pathlib.Path(str(final_path))


def truncate_mac(path, keep_suffix: str = "") -> pathlib.Path:
    """Shorten ``path``'s filename to fit ``MAC_MAX_PATH``."""
    path = pathlib.Path(os.path.normpath(path))
    dir_part = path.parent
    file_part, ext = split_extension(path.name, keep_suffix)
    max_bytes = of_env.getattr("MAC_MAX_PATH") - mac_name_size(ext)
    name = longest_fitting(file_part, mac_name_size, max_bytes)
    if (file_part and not name) or max_bytes < 0:
        raise ValueError(f"the name limit leaves no room for any of the name: {path}")
    new_file = f"{name}{ext}"
    log.debug(f"path: {path} filename bytesize: {mac_name_size(new_file)}")
    return pathlib.Path(dir_part, new_file)


def truncate_linux(path, keep_suffix: str = "") -> pathlib.Path:
    """Shorten ``path``'s filename to fit ``LINUX_MAX_FILE_NAME_BYTES``."""
    path = pathlib.Path(os.path.normpath(path))
    dir_part = path.parent
    file_part, ext = split_extension(path.name, keep_suffix)
    max_bytes = of_env.getattr("LINUX_MAX_FILE_NAME_BYTES") - unix_byte_size(ext)
    name = longest_fitting(file_part, unix_byte_size, max_bytes)
    if (file_part and not name) or max_bytes < 0:
        raise ValueError(f"the name limit leaves no room for any of the name: {path}")
    new_file = f"{name}{ext}"
    log.debug(f"path: {path} filename bytesize: {unix_byte_size(new_file)}")
    return pathlib.Path(dir_part, new_file)


def truncate(path, *, keep_suffix: str = "", system: str | None = None) -> pathlib.Path:
    """Shorten ``path`` to fit the active system's path/name limit while
    preserving its extension (or ``keep_suffix``)."""
    path = pathlib.Path(os.path.normpath(path))
    current_system = system if system is not None else platform.system()
    if current_system == "Windows":
        return truncate_windows(path, keep_suffix)
    if current_system == "Linux":
        return truncate_linux(path, keep_suffix)
    if current_system == "Darwin":
        return truncate_mac(path, keep_suffix)
    return pathlib.Path(path)


def validate_directory_parts(parts, *, system: str | None = None) -> None:
    """Reject a generated directory component that exceeds its platform's limit."""
    current_system = system if system is not None else platform.system()
    if current_system == "Windows":
        # 255 UTF-16 units; WINDOWS_MAX_PATH_BYTES is the whole path's
        size, limit = windows_byte_size, 510
    elif current_system == "Darwin":
        size, limit = mac_name_size, of_env.getattr("MAC_MAX_PATH")
    else:
        # real bytes: the estimate truncate() uses without UTF (2 per ASCII
        # character) would reject a folder name half the limit long
        size = lambda part: len(os.fsencode(part))  # noqa: E731
        limit = of_env.getattr("LINUX_MAX_FILE_NAME_BYTES")
    if any(size(part) > limit for part in parts):
        raise ValueError(
            "a livestream directory component exceeds the filesystem name limit"
        )
