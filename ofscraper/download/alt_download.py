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
import pathlib
import re
import traceback
from functools import partial

import aiofiles
import psutil

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.classes.placeholder as placeholder
import ofscraper.download.shared.common.general as common
import ofscraper.download.shared.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.download.shared.classes.retries import download_retry
from ofscraper.download.shared.common.alt_common import (
    handle_result_alt,
    media_item_keys_alt,
    media_item_post_process_alt,
)
from ofscraper.download.shared.common.general import (
    check_forced_skip,
    downloadspace,
    get_medialog,
    get_resume_size,
    size_checker,
)
from ofscraper.download.shared.utils.log import (
    get_url_log,
    path_to_file_logger,
    temp_file_logger,
)


async def alt_download(c, ele, username, model_id, job_progress):
    common_globals.log.debug(
        f"{get_medialog(ele)} Downloading with protected media downloader"
    )
    async for _ in download_retry():
        with _:
            try:
                sharedPlaceholderObj = await placeholder.Placeholders(ele, "mp4").init()
                common_globals.log.debug(
                    f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
                )
            except Exception as e:
                raise e

    audio, video = await ele.mpd_dict
    path_to_file_logger(sharedPlaceholderObj, ele)

    audio = await alt_download_downloader(audio, c, ele, job_progress)
    video = await alt_download_downloader(video, c, ele, job_progress)

    post_result = await media_item_post_process_alt(
        audio, video, ele, username, model_id
    )
    if post_result:
        return post_result
    await media_item_keys_alt(c, audio, video, ele)

    return await handle_result_alt(
        sharedPlaceholderObj, ele, audio, video, username, model_id
    )


async def alt_download_downloader(item, c, ele, job_progress):
    downloadspace(mediatype=ele.mediatype)
    placeholderObj = await placeholder.tempFilePlaceholder(
        ele, f"{item['name']}.part"
    ).init()
    item["path"] = placeholderObj.tempfilepath
    item["total"] = None
    async for _ in download_retry():
        with _:
            try:
                _attempt = common.alt_attempt_get(item)
                _attempt.set(_attempt.get(0) + 1)
                (
                    pathlib.Path(placeholderObj.tempfilepath).unlink(missing_ok=True)
                    if _attempt.get() > 1
                    else None
                )
                data = await asyncio.get_event_loop().run_in_executor(
                    common_globals.cache_thread,
                    partial(cache.get, f"{item['name']}_headers"),
                )
                if data:
                    return await main_data_handler(
                        data, item, c, ele, placeholderObj, job_progress
                    )

                else:
                    return await alt_data_handler(
                        item, c, ele, placeholderObj, job_progress
                    )
            except OSError as E:
                await asyncio.sleep(1)
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Number of Open Files -> { len(psutil.Process().open_files())}"
                )
                common_globals.log.debug(
                    f" {get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Open Files -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}"
                )
                raise E
            except Exception as E:
                await asyncio.sleep(1)
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] {traceback.format_exc()}"
                )
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] {E}"
                )
                raise E


async def main_data_handler(data, item, c, ele, placeholderObj, job_progress):
    item["total"] = int(data.get("content-length"))
    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    if await check_forced_skip(ele, item["total"]):
        item["total"] = 0
        return item
    elif item["total"] == resume_size:
        temp_file_logger(placeholderObj, ele)
        return item
    elif item["total"] != resume_size:
        return await alt_download_sendreq(item, c, ele, placeholderObj, job_progress)


async def alt_data_handler(item, c, ele, placeholderObj, job_progress):
    result = None
    try:
        result = await alt_download_sendreq(item, c, ele, placeholderObj, job_progress)
    except Exception as E:
        raise E
    return result


async def alt_download_sendreq(item, c, ele, placeholderObj, job_progress):
    try:
        _attempt = common.alt_attempt_get(item)
        item["total"] = item["total"] if _attempt == 1 else None
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"
        common_globals.log.debug(
            f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
        )
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] download temp path {placeholderObj.tempfilepath}"
        )
        return await send_req_inner(c, ele, item, placeholderObj, job_progress)
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, item, placeholderObj, job_progress):
    old_total = item["total"]
    total = old_total
    try:
        await common.total_change_helper(None, total)
        resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
        headers = (
            None
            if resume_size == 0 or not total
            else {"Range": f"bytes={resume_size}-{total}"}
        )
        params = {
            "Policy": ele.policy,
            "Key-Pair-Id": ele.keypair,
            "Signature": ele.signature,
        }
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"

        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common.alt_attempt_get(item).get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Downloading media with url {url}"
        )
        async with c.requests_async(url=url, headers=headers, params=params) as l:
            await asyncio.get_event_loop().run_in_executor(
                common_globals.cache_thread,
                partial(
                    cache.set,
                    f"{item['name']}_headers",
                    {
                        "content-length": l.headers.get("content-length"),
                        "content-type": l.headers.get("content-type"),
                    },
                ),
            )
            new_total = int(l.headers["content-length"])
            temp_file_logger(placeholderObj, ele)
            if await check_forced_skip(ele, new_total):
                item["total"] = 0
                await common.total_change_helper(None, old_total)
            elif total != resume_size:
                item["total"] = new_total
                total = new_total
                await common.total_change_helper(old_total, total)
                await download_fileobject_writer(
                    total, l, ele, job_progress, placeholderObj
                )
        await size_checker(placeholderObj.tempfilepath, ele, total)
        return item
    except Exception as E:
        await common.total_change_helper(None, -(total or 0))
        raise E


async def download_fileobject_writer(total, l, ele, job_progress, placeholderObj):
    pathstr = str(placeholderObj.tempfilepath)

    downloadprogress = settings.get_download_bars()

    task1 = job_progress.add_task(
        f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
        total=total,
        visible=True if downloadprogress else False,
    )
    count = 0
    loop = asyncio.get_event_loop()

    fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
    download_sleep = constants.getattr("DOWNLOAD_SLEEP")
    try:
        async for chunk in l.iter_chunked(constants.getattr("maxChunkSize")):
            if downloadprogress:
                count = count + 1
            common_globals.log.trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(placeholderObj.tempfilepath).absolute().stat().st_size)}/{total}"
            )
            await fileobject.write(chunk)
            if (count + 1) % constants.getattr("CHUNK_ITER") == 0:
                await loop.run_in_executor(
                    common_globals.thread,
                    partial(
                        job_progress.update,
                        task1,
                        completed=pathlib.Path(placeholderObj.tempfilepath)
                        .absolute()
                        .stat()
                        .st_size,
                    ),
                )
            (await asyncio.sleep(download_sleep)) if download_sleep else None
    except Exception as E:
        raise E
    finally:
        # Close file if needed
        try:
            await fileobject.close()
        except Exception:
            None

        try:
            job_progress.remove_task(task1)
        except Exception:
            None
