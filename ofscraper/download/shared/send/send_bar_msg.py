import asyncio
import ofscraper.download.shared.general as common
import ofscraper.download.shared.globals.globals as common_globals

import ofscraper.utils.settings as settings


async def send_bar_msg_batch(msg,count,update_count):
    if count%update_count != 0:
        return
    elif not settings.get_download_bars():
        return
    await common.send_msg(msg)



async def send_bar_msg(func,count,update_count):
    if count%update_count != 0:
        return
    elif not settings.get_download_bars():
        return
    await asyncio.get_event_loop().run_in_executor(
        common_globals.thread,

        func
    )

