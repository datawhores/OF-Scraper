"""Byte counts shown and entered as a whole number and a unit.

Units are 1024-based (1 KB = 1,024 bytes), as file managers show sizes.
"""

KB = 1024
MB = KB * 1024
GB = MB * 1024
TB = GB * 1024

# (button label, bytes per unit), smallest first
UNITS = (("Bytes", 1), ("KB", KB), ("MB", MB), ("GB", GB))
NAMES = {value: label for label, value in UNITS}


def split_size(size):
    """``size`` bytes as (number, unit), in the largest unit it divides into
    exactly, so a saved value is shown unchanged. 0 is (0, MB)."""
    try:
        size = int(size or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return 0, MB
    for _, unit in reversed(UNITS):
        if size % unit == 0:
            return size // unit, unit
    return size, 1


def format_size(size):
    """e.g. "10 MB", "1,500 Bytes", "0"."""
    number, unit = split_size(size)
    if number == 0:
        return "0"
    return f"{number:,} {NAMES[unit]}"


def parse_whole_number(text):
    """The number typed in a size box, or None if it isn't a whole number.
    An empty box is 0 (no limit)."""
    text = (text or "").strip().replace(",", "")
    if text == "":
        return 0
    if not text.isdecimal() or not text.isascii():
        return None
    return int(text)
