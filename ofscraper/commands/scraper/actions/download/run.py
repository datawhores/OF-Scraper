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

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.live.updater as progress_updater
from ofscraper.commands.scraper.actions.utils.log import (
    log_download_progress,
)
from ofscraper.commands.scraper.actions.utils.log import get_medialog

from ofscraper.commands.scraper.actions.utils.progress.convert import convert_num_bytes
from ofscraper.commands.scraper.actions.download.utils.desc import desc
from ofscraper.commands.scraper.actions.download.managers.alt_download import (
    AltDownloadManager,
)
from ofscraper.commands.scraper.actions.download.managers.main_download import (
    MainDownloadManager,
)
from ofscraper.commands.scraper.actions.download.managers.fansly_stream_download import (
    FanslyStreamDownloadManager,
)
from ofscraper.classes.of.media import Media
from ofscraper.sites.fansly import video as fansly_video


async def consumer(aws, task1, medialist, lock, on_result=None):
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
                ele: Media = data[1]
                pack = await download(*data)
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
                media_type = media_type.lower()
                if media_type == "images":
                    common_globals.photo_count += 1
                    ele.mark_download_succeeded()

                elif media_type == "videos":
                    common_globals.video_count += 1
                    ele.mark_download_succeeded()
                elif media_type == "audios":
                    common_globals.audio_count += 1
                    ele.mark_download_succeeded()
                elif media_type == "skipped":
                    common_globals.skipped += 1
                    ele.mark_download_failed()
                elif media_type == "forced_skipped":
                    ele.mark_download_skipped()
                    common_globals.forced_skipped += 1
                if on_result is not None:
                    result = (
                        "failed" if media_type == "skipped"
                        else "skipped" if media_type == "forced_skipped"
                        else "downloaded"
                    )
                    on_result(ele, result)
                sum_count = (
                    common_globals.photo_count
                    + common_globals.video_count
                    + common_globals.audio_count
                    + common_globals.skipped
                    + common_globals.forced_skipped
                )
                log_download_progress(media_type)
                progress_updater.download.update_overall_task(
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


async def download(c, ele, model_id, username):
    try:
        data = None
        # skip_download_script's answers last for this download call and its
        # retries: the check table sends the same Media again, and it's
        # asked again then, as before (#350)
        ele.skip_script_answers = {}
        if fansly_video.uses_stream(ele):
            # None: the stream can't be used and the item has a direct file
            data = await FanslyStreamDownloadManager().stream_download(
                c, ele, username, model_id
            )
        if data is None and ele.url:
            data = await MainDownloadManager().main_download(
                c,
                ele,
                username,
                model_id,
            )
        elif data is None and ele.mpd:
            data = await AltDownloadManager().alt_download(c, ele, username, model_id)
        common_globals.log.debug(f"{get_medialog(ele)} Download finished")
        return data
    except Exception as E:
        common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
        common_globals.log.debug(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        return "skipped", 0
