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
import traceback
from functools import partial

import aiofiles
import psutil

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.classes.placeholder as placeholder
import ofscraper.download.shared.general as common
import ofscraper.download.shared.globals.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
from ofscraper.download.shared.classes.retries import download_retry
from ofscraper.download.shared.general import (
    check_forced_skip,
    downloadspace,
    get_data,
    get_medialog,
    get_resume_size,
    get_unknown_content_type,
    size_checker,
)
from ofscraper.download.shared.handle_result import handle_result_main
from ofscraper.download.shared.log import get_url_log, path_to_file_logger
from ofscraper.download.shared.metadata import force_download
from ofscraper.download.shared.send.send_bar_msg import (
    send_bar_msg
)
from ofscraper.download.shared.progress.chunk import (
    get_ideal_chunk_size,
    get_update_count,
)


async def main_download(c, ele, username, model_id):
    common_globals.log.debug(f"{get_medialog(ele)} Downloading with normal downloader")
    common_globals.log.debug(f"{get_medialog(ele)} download url:  {get_url_log(ele)}")
    if common.is_bad_url(ele.url):
        common_globals.log.debug(
            f"{get_medialog(ele)} Forcing download because known bad url"
        )
        await force_download(ele, username, model_id)
        return ele.mediatype, 0
    result = await main_download_downloader(
        c,
        ele,
    )

    # special case for zero byte files
    if result[0] == 0:
        if ele.mediatype != "forced_skipped":
            await force_download(ele, username, model_id)
        return ele.mediatype, 0
    return await handle_result_main(result, ele, username, model_id)


async def main_download_downloader(c, ele):
    downloadspace(mediatype=ele.mediatype)
    tempholderObj = await placeholder.tempFilePlaceholder(
        ele, f"{await ele.final_filename}_{ele.id}.part"
    ).init()
    async for _ in download_retry():
        with _:
            try:
                data = await get_data(ele)
                common_globals.attempt.set(common_globals.attempt.get(0) + 1)
                (
                    pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
                    if common_globals.attempt.get() > 1
                    else None
                )
                if data:
                    return await resume_data_handler(data, c, tempholderObj, ele)
                else:
                    return await fresh_data_handler(c, tempholderObj, ele)
            except OSError as E:
                # await asyncio.sleep(1)
                common_globals.log.debug(
                    f"[attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Number of Open Files -> { len(psutil.Process().open_files())}"
                )
                common_globals.log.debug(
                    f"[attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Open Files  -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}"
                )
                raise E
            except Exception as E:
                # await asyncio.sleep(1)
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] {traceback.format_exc()}"
                )
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] {E}"
                )
                raise E


async def fresh_data_handler(c, tempholderObj, ele):
    result = None
    try:
        result = await main_download_sendreq(
            c, ele, tempholderObj, placeholderObj=None, total=None
        )
    except Exception as E:
        raise E
    return result


async def resume_data_handler(data, c, tempholderObj, ele):
    content_type = data.get("content-type").split("/")[-1]
    total = int(data.get("content-total")) if data.get("content-total") else None
    placeholderObj = await placeholder.Placeholders(ele, content_type).init()
    resume_size = get_resume_size(tempholderObj, mediatype=ele.mediatype)
    # other
    if await check_forced_skip(ele, total) == 0:
        path_to_file_logger(placeholderObj, ele)
        return [0]
    elif total == resume_size:
        (
            await common.total_change_helper(None, total)
            if common_globals.attempt.get() == 1
            else None
        )
        path_to_file_logger(placeholderObj, ele)
        return (
            total,
            tempholderObj.tempfilepath,
            placeholderObj,
        )

    else:
        try:
            return await main_download_sendreq(
                c,
                ele,
                tempholderObj,
                total=total,
                placeholderObj=placeholderObj,
            )
        except Exception as E:
            raise E


async def main_download_sendreq(c, ele, tempholderObj, total=None, placeholderObj=None):
    try:
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] download temp path {tempholderObj.tempfilepath}"
        )
        return await send_req_inner(
            c,
            ele,
            tempholderObj,
            placeholderObj=placeholderObj,
            total=total,
        )
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, tempholderObj, placeholderObj=None, total=None):
    try:
        resume_size = get_resume_size(tempholderObj, mediatype=ele.mediatype)
        headers = None if not resume_size else {"Range": f"bytes={resume_size}-"}
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Downloading media with url {ele.url}"
        )
        async with c.requests_async(url=ele.url, headers=headers) as r:
            total = total or int(r.headers["content-length"])
            await common.total_change_helper(None, total)
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(
                    cache.set,
                    f"{ele.id}_headers",
                    {
                        "content-total": total,
                        "content-type": r.headers.get("content-type"),
                    },
                ),
            )
            content_type = r.headers.get("content-type").split("/")[-1]
            content_type = content_type or get_unknown_content_type(ele)
            if not placeholderObj:
                placeholderObj = await placeholder.Placeholders(
                    ele, content_type
                ).init()
            path_to_file_logger(placeholderObj, ele)
            if await check_forced_skip(ele, total) == 0:
                total = 0
                await common.total_change_helper(total, 0)
            elif total != resume_size:
                total = total
                await download_fileobject_writer(
                    r, ele, tempholderObj, placeholderObj, total
                )

        await size_checker(tempholderObj.tempfilepath, ele, total)
        return (total, tempholderObj.tempfilepath, placeholderObj)
    except Exception as E:
        await common.total_change_helper(total, 0)
        raise E


async def download_fileobject_writer(r, ele, tempholderObj, placeholderObj, total):
    pathstr = str(placeholderObj.trunicated_filepath)
    task1 = progress_utils.add_download_job_task(
        f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
        total=total,
    )
    try:
        loop = asyncio.get_event_loop()
        fileobject = await aiofiles.open(tempholderObj.tempfilepath, "ab").__aenter__()
        download_sleep = constants.getattr("DOWNLOAD_SLEEP")
        chunk_size = get_ideal_chunk_size(total, tempholderObj.tempfilepath)
        update_count = get_update_count(total, tempholderObj.tempfilepath, chunk_size)
        count = 1
        async for chunk in r.iter_chunked(chunk_size):
            await fileobject.write(chunk)
            common_globals.log.trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(tempholderObj.tempfilepath).absolute().stat().st_size)}/{total}"
            )
            await send_bar_msg( partial(
                        progress_utils.update_download_job_task,
                        task1,
                        completed=pathlib.Path(tempholderObj.tempfilepath)
                        .absolute()
                        .stat()
                        .st_size,
            ),count,update_count)

            count += 1
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
            progress_utils.remove_downloadjob_task(task1)
        except Exception:
            None
