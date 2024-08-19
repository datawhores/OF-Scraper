import math
from humanfriendly import format_size


def convert_num_bytes(num_bytes: int) -> str:
    try:
        return format_size(num_bytes)
    except Exception:
        if num_bytes <= 0:
            return "0 B"
        num_digits = int(math.log10(num_bytes)) + 1
        if num_digits >= 10:
            return f"{round(num_bytes / 10**9, 2)} GB"
        return f"{round(num_bytes / 10 ** 6, 2)} MB"
