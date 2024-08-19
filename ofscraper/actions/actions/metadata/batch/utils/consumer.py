import platform
import traceback

from ofscraper.actions.utils.send.message import send_msg
from ofscraper.actions.actions.metadata.managers.metadata import MetaDataManager
import ofscraper.actions.utils.globals as common_globals


platform_name = platform.system()


async def consumer(lock, aws):
    while True:
        async with lock:
            if not (bool(aws)):
                break
            data = aws.pop()
        if data is None:
            break
        else:
            try:
                media_type = await MetaDataManager(multi=True).metadata(*data)
                await send_msg(media_type)
            except Exception as e:
                common_globals.log.info(f"Download Failed because\n{e}")
                common_globals.log.traceback_(traceback.format_exc())
                media_type = "skipped"
                await send_msg(media_type)
