import asyncio

import ofscraper.download.utils.globals as common_globals
from ofscraper.download.utils.send.message import send_msg_alt
import ofscraper.utils.settings as settings



async def send_bar_msg_batch(msg, count, update_count):
    if not settings.get_download_bars():
        return
    await send_msg_alt(msg)


async def send_bar_msg(func, count, update_count):
    if not settings.get_download_bars():
        return
    await asyncio.get_event_loop().run_in_executor(common_globals.thread, func)
