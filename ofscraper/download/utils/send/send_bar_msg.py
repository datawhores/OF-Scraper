import asyncio

import ofscraper.download.utils.general as common
import ofscraper.download.utils.globals as common_globals
import ofscraper.utils.settings as settings
from ofscraper.download.utils.send.message import send_msg


async def send_bar_msg_batch(msg, count, update_count):
    if count % update_count != 0:
        return
    elif not settings.get_download_bars():
        return
    await send_msg(msg)


async def send_bar_msg(func, count, update_count):
    if count % update_count != 0:
        return
    elif not settings.get_download_bars():
        return
    await asyncio.get_event_loop().run_in_executor(common_globals.thread, func)
