import platform
import traceback

from ofscraper.actions.utils.send.message import send_msg
from ofscraper.actions.actions.download.runners.download import download
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
                pack = await download(*data, multi=True)
                common_globals.log.debug(f"unpack {pack} count {len(pack)}")
                media_type, num_bytes_downloaded = pack
                await send_msg((media_type, num_bytes_downloaded, 0))
            except Exception as e:
                common_globals.log.info(f"Download Failed because\n{e}")
                common_globals.log.traceback_(traceback.format_exc())
                media_type = "skipped"
                num_bytes_downloaded = 0
                await send_msg((media_type, num_bytes_downloaded, 0))
