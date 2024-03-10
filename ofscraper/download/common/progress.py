import math

from rich.console import Group
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Column

import ofscraper.download.common.globals as common_globals
import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.console as console_
from ofscraper.classes.multiprocessprogress import MultiprocessProgress as MultiProgress


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
