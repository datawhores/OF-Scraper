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
import logging
import traceback

from humanfriendly import format_size
from rich.live import Live

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.download.common.common as common
import ofscraper.download.common.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.context.stdout as stdout
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.other as other_logs
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.manager as manager_
from ofscraper.download.alt_download import alt_download
from ofscraper.download.common.common import (
    convert_num_bytes,
    get_medialog,
    log_download_progress,
    setDirectoriesDate,
)
from ofscraper.download.main_download import main_download
from ofscraper.utils.context.run_async import run
from ofscraper.utils.progress import setupDownloadProgressBar


@run
async def process_dicts(username, model_id, medialist):
    with stdout.lowstdout():
        progress_group, overall_progress, job_progress = setupDownloadProgressBar()
        # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8
        common_globals.reset_globals()

        try:
            manager = manager_.get_manager()
            logqueue = manager.Queue()
            otherqueue = manager.Queue()
            download_log = logger.get_shared_logger(
                name="ofscraper_download", main_=logqueue, other_=otherqueue
            )
            common_globals.log = download_log
            # start stdout/main queues consumers
            log_thread = stdout_logs.start_stdout_logthread(
                input_=logqueue, name="ofscraper_normal_stdout"
            )
            other_thread = other_logs.start_other_thread(
                input_=otherqueue, name="ofscraper_normal_other"
            )
            with Live(
                progress_group,
                refresh_per_second=constants.getattr("refreshScreen"),
                console=console.shared_console,
            ):
                aws = []
                desc = "Progress: ({p_count} photos, {v_count} videos, {a_count} audios, {forced_skipped} skipped, {skipped} failed || {sumcount}/{mediacount}||{total_bytes_download}/{total_bytes})"

                async with sessionbuilder.sessionBuilder() as c:
                    for ele in medialist:
                        aws.append(
                            asyncio.create_task(
                                download(c, ele, model_id, username, job_progress)
                            )
                        )
                    task1 = overall_progress.add_task(
                        desc.format(
                            p_count=common_globals.photo_count,
                            v_count=common_globals.video_count,
                            a_count=common_globals.audio_count,
                            skipped=common_globals.skipped,
                            mediacount=len(medialist),
                            forced_skipped=common_globals.forced_skipped,
                            sumcount=0,
                            total_bytes_download=0,
                            total_bytes=0,
                        ),
                        total=len(aws),
                        visible=True,
                    )
                    for coro in asyncio.as_completed(aws):
                        try:
                            pack = await coro
                            common_globals.log.debug(f"unpack {pack} count {len(pack)}")
                            media_type, num_bytes_downloaded = pack
                        except Exception as e:
                            common_globals.log.traceback_(
                                f"Download Failed because\n{e}"
                            )
                            common_globals.log.traceback_(traceback.format_exc())
                            media_type = "skipped"
                            num_bytes_downloaded = 0

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
                        overall_progress.update(
                            task1,
                            description=desc.format(
                                p_count=common_globals.photo_count,
                                v_count=common_globals.video_count,
                                a_count=common_globals.audio_count,
                                skipped=common_globals.skipped,
                                forced_skipped=common_globals.forced_skipped,
                                mediacount=len(medialist),
                                sumcount=sum_count,
                                total_bytes=convert_num_bytes(
                                    common_globals.total_bytes
                                ),
                                total_bytes_download=convert_num_bytes(
                                    common_globals.total_bytes_downloaded
                                ),
                            ),
                            refresh=True,
                            advance=1,
                        )
            overall_progress.remove_task(task1)
            setDirectoriesDate()
            # close thread
            otherqueue.put("None")
            logqueue.put("None")
            log_thread.join()
            other_thread.join() if other_thread else None
            common.final_log(username, log=logging.getLogger("shared"))
            return (
                common_globals.photo_count,
                common_globals.video_count,
                common_globals.audio_count,
                common_globals.forced_skipped,
                common_globals.skipped,
            )

        except Exception as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        finally:
            await asyncio.get_event_loop().run_in_executor(
                common_globals.cache_thread, cache.close
            )
            common_globals.cache_thread.shutdown()


async def download(c, ele, model_id, username, progress):
    async with common_globals.maxfile_sem:
        try:
            if ele.url:
                return await main_download(
                    c,
                    ele,
                    username,
                    model_id,
                    progress,
                )
            elif ele.mpd:
                return await alt_download(
                    c,
                    ele,
                    username,
                    model_id,
                    progress,
                )
        except Exception as E:
            common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
            common_globals.log.debug(
                f"{get_medialog(ele)} exception {traceback.format_exc()}"
            )
            return "skipped", 0
