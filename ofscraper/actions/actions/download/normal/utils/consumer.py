r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import asyncio
import traceback

import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.live.updater as progress_updater
from ofscraper.actions.utils.log import (
    log_download_progress,
)
from ofscraper.actions.utils.log import get_medialog
from ofscraper.actions.actions.download.runners.download import download

from ofscraper.actions.utils.progress.convert import convert_num_bytes
from ofscraper.actions.actions.download.utils.desc import desc


async def consumer(aws, task1, medialist, lock):

    while True:
        ele = None
        async with lock:
            if not (bool(aws)):
                break
            data = aws.pop()
        if data is None:
            break
        else:
            try:
                ele = data[1]
                pack = await download(*data, multi=False)
                common_globals.log.debug(f"unpack {pack} count {len(pack)}")
                media_type, num_bytes_downloaded = pack
            except Exception as e:
                common_globals.log.info(
                    f"{get_medialog(ele)} Download Failed because\n{e}"
                )
                common_globals.log.traceback_(traceback.format_exc())
                media_type = "skipped"
                num_bytes_downloaded = 0
            try:
                common_globals.total_bytes_downloaded = (
                    common_globals.total_bytes_downloaded + num_bytes_downloaded
                )
                if media_type == "images":
                    common_globals.photo_count += 1

                elif media_type == "videos":
                    common_globals.video_count += 1
                elif media_type == "audios":
                    common_globals.audio_count += 1
                elif media_type == "skipped":
                    common_globals.skipped += 1
                elif media_type == "forced_skipped":
                    common_globals.forced_skipped += 1
                sum_count = (
                    common_globals.photo_count
                    + common_globals.video_count
                    + common_globals.audio_count
                    + common_globals.skipped
                    + common_globals.forced_skipped
                )
                log_download_progress(media_type)
                progress_updater.update_download_task(
                    task1,
                    description=desc.format(
                        p_count=common_globals.photo_count,
                        v_count=common_globals.video_count,
                        a_count=common_globals.audio_count,
                        skipped=common_globals.skipped,
                        forced_skipped=common_globals.forced_skipped,
                        mediacount=len(medialist),
                        sumcount=sum_count,
                        total_bytes=convert_num_bytes(common_globals.total_bytes),
                        total_bytes_download=convert_num_bytes(
                            common_globals.total_bytes_downloaded
                        ),
                    ),
                    refresh=True,
                    advance=1,
                )
                await asyncio.sleep(1)
            except Exception as e:
                common_globals.log.info(
                    f"{get_medialog(ele)} Download Failed because\n{e}"
                )
                common_globals.log.traceback_(traceback.format_exc())
