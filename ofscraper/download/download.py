r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import logging
import pathlib
import traceback

from rich.live import Live
from rich.table import Column

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.classes.placeholder as placeholder
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.constants as constants
import ofscraper.download.common as common
import ofscraper.utils.console as console
import ofscraper.utils.exit as exit
import ofscraper.utils.paths as paths
import ofscraper.utils.stdout as stdout
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.download.alt_download import alt_download
from ofscraper.download.common import (
    convert_num_bytes,
    get_medialog,
    reset_globals,
    setDirectoriesDate,
    setupProgressBar,
)
from ofscraper.download.main_download import main_download
from ofscraper.utils.run_async import run


@run
async def process_dicts(username, model_id, medialist):
    with stdout.lowstdout():
        progress_group, overall_progress, job_progress = setupProgressBar()
        # This need to be here: https://stackoverflow.com/questions/73599594/asyncio-works-in-python-3-10-but-not-in-python-3-8
        reset_globals()
        common.log = logging.getLogger("ofscraper-download")

        try:
            with Live(
                progress_group,
                refresh_per_second=constants.refreshScreen,
                console=console.shared_console,
            ):
                aws = []
                photo_count = 0
                video_count = 0
                audio_count = 0
                skipped = 0
                forced_skipped = 0
                total_downloaded = 0
                sum = 0
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
                            p_count=photo_count,
                            v_count=video_count,
                            a_count=audio_count,
                            skipped=skipped,
                            mediacount=len(medialist),
                            forced_skipped=forced_skipped,
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
                            common.log.debug(f"unpack {pack} count {len(pack)}")
                            media_type, num_bytes_downloaded = pack
                        except Exception as e:
                            common.log.traceback_(e)
                            common.log.traceback_(traceback.format_exc())
                            media_type = "skipped"
                            num_bytes_downloaded = 0

                        total_downloaded += num_bytes_downloaded
                        total_bytes_downloaded = convert_num_bytes(total_downloaded)
                        total_bytes = convert_num_bytes(common.total_data)
                        if media_type == "images":
                            photo_count += 1

                        elif media_type == "videos":
                            video_count += 1
                        elif media_type == "audios":
                            audio_count += 1
                        elif media_type == "skipped":
                            skipped += 1
                        elif media_type == "forced_skipped":
                            forced_skipped += 1
                        sum += 1
                        overall_progress.update(
                            task1,
                            description=desc.format(
                                p_count=photo_count,
                                v_count=video_count,
                                a_count=audio_count,
                                skipped=skipped,
                                forced_skipped=forced_skipped,
                                mediacount=len(medialist),
                                sumcount=sum,
                                total_bytes=total_bytes,
                                total_bytes_download=total_bytes_downloaded,
                            ),
                            refresh=True,
                            advance=1,
                        )
            overall_progress.remove_task(task1)
            setDirectoriesDate()
            common.log.warning(
                f"[bold]{username}[/bold] ({photo_count+audio_count+video_count} downloads total [{video_count} videos, {audio_count} audios, {photo_count} photos]  {forced_skipped} skipped, {skipped} failed)"
            )
            return photo_count, video_count, audio_count, forced_skipped, skipped

        except Exception as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        finally:
            await asyncio.get_event_loop().run_in_executor(
                common.cache_thread, common.cache.close
            )
            common.cache_thread.shutdown()


async def download(c, ele, model_id, username, progress):
    async with common.maxfile_sem:
        with paths.set_directory(
            placeholder.Placeholders().getmediadir(ele, username, model_id)
        ):
            try:
                if ele.url:
                    return await main_download(
                        c,
                        ele,
                        pathlib.Path(".").absolute(),
                        username,
                        model_id,
                        progress,
                    )
                elif ele.mpd:
                    return await alt_download(
                        c,
                        ele,
                        pathlib.Path(".").absolute(),
                        username,
                        model_id,
                        progress,
                    )
            except Exception as E:
                common.log.debug(f"{get_medialog(ele)} exception {E}")
                common.log.debug(
                    f"{get_medialog(ele)} exception {traceback.format_exc()}"
                )
                return "skipped", 0
