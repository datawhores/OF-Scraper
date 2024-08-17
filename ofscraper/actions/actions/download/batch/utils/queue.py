import asyncio
import logging
import logging.handlers
import platform
import traceback

import ofscraper.actions.utils.globals as common_globals

import ofscraper.utils.live.updater as progress_updater
from ofscraper.actions.utils.log import (
    log_download_progress,
)

from ofscraper.actions.utils.paths.paths import addGlobalDir
from ofscraper.actions.utils.progress.convert import convert_num_bytes
from ofscraper.actions.actions.download.utils.desc import desc

platform_name = platform.system()


def queue_process(pipe_, task1, total):
    count = 0
    while True:
        try:
            if count == 1:
                break
            try:
                if not pipe_.poll(timeout=1):
                    continue
                results = pipe_.recv()
                if not isinstance(results, list):
                    results = [results]
            except Exception as E:
                common_globals.log.traceback_(E)
                common_globals.log.traceback_(traceback.format_exc())
                continue
            for result in results:
                try:
                    if isinstance(result, list) or isinstance(result, tuple):
                        media_type, num_bytes_downloaded, total_size = result
                        with common_globals.count_lock:
                            common_globals.total_bytes_downloaded = (
                                common_globals.total_bytes_downloaded
                                + num_bytes_downloaded
                            )
                            common_globals.total_bytes = (
                                common_globals.total_bytes + total_size
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
                            log_download_progress(media_type)
                            progress_updater.update_download_task(
                                task1,
                                description=desc.format(
                                    p_count=common_globals.photo_count,
                                    v_count=common_globals.video_count,
                                    a_count=common_globals.audio_count,
                                    skipped=common_globals.skipped,
                                    forced_skipped=common_globals.forced_skipped,
                                    total_bytes_download=convert_num_bytes(
                                        common_globals.total_bytes_downloaded
                                    ),
                                    total_bytes=convert_num_bytes(
                                        common_globals.total_bytes
                                    ),
                                    mediacount=total,
                                    sumcount=common_globals.video_count
                                    + common_globals.audio_count
                                    + common_globals.photo_count
                                    + common_globals.skipped
                                    + common_globals.forced_skipped,
                                ),
                                refresh=True,
                                completed=common_globals.video_count
                                + common_globals.audio_count
                                + common_globals.photo_count
                                + common_globals.skipped
                                + common_globals.forced_skipped,
                            )

                    elif result is None or result == "None":
                        count = count + 1
                    elif isinstance(result, dict) and "dir_update" in result:
                        addGlobalDir(result["dir_update"])
                    elif callable(result):
                        job_progress_helper(result)
                except Exception as E:
                    common_globals.log.traceback_(E)
                    common_globals.log.traceback_(traceback.format_exc())
                    # increase skipped
                    common_globals.skipped += 1
        except Exception as E:
            common_globals.log.traceback_(E)
            common_globals.log.traceback_(traceback.format_exc())
            # increase skipped


def job_progress_helper(funct):
    try:
        funct()
    # probably handle by other thread
    except KeyError:
        pass
    except Exception as E:
        logging.getLogger("shared").debug(E)


async def ajob_progress_helper(funct):
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            funct,
        )
    # probably handle by other thread
    except KeyError:
        pass
    except Exception as E:
        logging.getLogger("shared").debug(E)
