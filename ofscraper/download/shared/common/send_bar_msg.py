import asyncio
import ofscraper.download.shared.common.general as common
import ofscraper.download.shared.globals as common_globals
# import ofscraper.utils.cache as cache
# import ofscraper.utils.constants as constants
# import ofscraper.utils.live.screens as progress_utils
# import ofscraper.utils.system.system as system
# from ofscraper.download.shared.classes.retries import download_retry
# from ofscraper.download.shared.common.alt_common import (
#     handle_result_alt,
#     media_item_keys_alt,
#     media_item_post_process_alt,
# )
# from ofscraper.download.shared.common.general import (
#     check_forced_skip,
#     downloadspace,
#     get_ideal_chunk_size,
#     get_medialog,
#     get_resume_size,
#     get_update_count,
#     size_checker,
# )
# from ofscraper.download.shared.utils.log import (
#     get_url_log,
#     path_to_file_logger,
#     temp_file_logger,
# )
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

