import math

import ofscraper.download.common.globals as common_globals


def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
        return "0 B"
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f"{round(num_bytes / 10**9, 2)} GB"
    return f"{round(num_bytes / 10 ** 6, 2)} MB"


async def update_total(update):
    async with common_globals.lock:
        common_globals.total_bytes += update
