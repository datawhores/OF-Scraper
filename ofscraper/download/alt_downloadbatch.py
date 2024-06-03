import asyncio
import pathlib
import re
import traceback
from functools import partial
from humanfriendly import format_size
import aiofiles

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
import ofscraper.utils.system.system as system
from ofscraper.download.shared.classes.retries import download_retry,get_download_retries
from ofscraper.download.shared.alt_common import (
    media_item_keys_alt,
    media_item_post_process_alt,
)
from ofscraper.download.shared.handle_result import (
    handle_result_alt,
)
from ofscraper.download.shared.general import (
    check_forced_skip,
    downloadspace,
    get_medialog,
    get_resume_size,
    size_checker,
)
from ofscraper.download.shared.log import (
    get_url_log,
    path_to_file_logger,
    temp_file_logger,
)

from ofscraper.download.shared.progress.chunk import (
    get_ideal_chunk_size,
    get_update_count,
)
from ofscraper.download.shared.send.send_bar_msg import (
    send_bar_msg_batch
)

from ofscraper.download.shared.send.chunk import (
    send_chunk_msg
)


async def alt_download(c, ele, username, model_id):
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} Downloading with batch protected media downloader"
    )
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
    )
    async for _ in download_retry():
        with _:
            try:
                sharedPlaceholderObj = await placeholder.Placeholders(ele, "mp4").init()
                audio, video = await ele.mpd_dict
            except Exception as e:
                common_globals.log.traceback_(e)
                common_globals.log.traceback_(traceback.format_exc())
                common_globals.log.handlers[1].queue.put(
                list(common_globals.innerlog.get().handlers[1].queue.queue)
                )
                common_globals.log.handlers[0].queue.put(
                list(common_globals.innerlog.get().handlers[0].queue.queue)
                )
                raise e
    path_to_file_logger(sharedPlaceholderObj, ele, common_globals.innerlog.get())
    audio = await alt_download_downloader(audio, c, ele)
    video = await alt_download_downloader(video, c, ele)

    post_result = await media_item_post_process_alt(
        audio, video, ele, username, model_id
    )
    if post_result:
        return post_result
    await media_item_keys_alt(c, audio, video, ele)
    return await handle_result_alt(
        sharedPlaceholderObj, ele, audio, video, username, model_id
    )


async def alt_download_downloader(
    item,
    c,
    ele,
):
    downloadspace(mediatype=ele.mediatype)
    placeholderObj = placeholder.tempFilePlaceholder(ele, f"{item['name']}.part")
    await placeholderObj.init()
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
                    common_globals.thread,
                    partial(cache.get, f"{item['name']}_headers"),
                )
                if data:
                    return await resume_data_handler(data, item, c, ele, placeholderObj)
                else:
                    return await fresh_data_handler(item, c, ele, placeholderObj)
            except OSError as E:
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] Number of unique open files across all processes-> {len(system.getOpenFiles())}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}"
                )
                raise E
            except Exception as E:
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] {traceback.format_exc()}"
                )
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] {E}"
                )
                common_globals.log.handlers[1].queue.put(
                list(common_globals.innerlog.get().handlers[1].queue.queue)
                )
                common_globals.log.handlers[0].queue.put(
                list(common_globals.innerlog.get().handlers[0].queue.queue)
                )
                raise E


async def resume_data_handler(data, item, c, ele, placeholderObj):
    common_globals.log.debug(f"{get_medialog(ele)} Data from cache{data}")
    common_globals.log.debug(f"{get_medialog(ele)} Total size from cache {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}")
    total=(
        int(data.get("content-total")) if data.get("content-total") else None
    )
    item["total"] = total

    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    common_globals.log.debug(f"{get_medialog(ele)} resume_size: {resume_size}  and total: {total }")
    if await check_forced_skip(ele,total) == 0:
        item["total"] = 0
        return item
    elif total == resume_size:
        common_globals.log.debug(f"{get_medialog(ele)} total==resume_size skipping download")

        (

            await common.batch_total_change_helper(None, total)
            if common.alt_attempt_get(item).get() == 1
            else None
        )
        return item
    elif item["total"] != resume_size:
        return await alt_download_sendreq(item, c, ele, placeholderObj)


async def fresh_data_handler(item, c, ele, placeholderObj):
    common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] fresh download for media"
    )
    result = None
    try:
        result = await alt_download_sendreq(item, c, ele, placeholderObj)
    except Exception as E:
        raise E
    return result


async def alt_download_sendreq(item, c, ele, placeholderObj):
    _attempt = common.alt_attempt_get(item)
    base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
    url = f"{base_url}{item['origname']}"
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
    )
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] download temp path {placeholderObj.tempfilepath}"
    )
    try:
        item["total"] = item["total"] if _attempt == 1 else None
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"
        common_globals.log.debug(
            f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
        )
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] download temp path {placeholderObj.tempfilepath}"
        )
        return await send_req_inner(c, ele, item, placeholderObj)
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, item, placeholderObj):
    total=None
    try:        
        resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
        headers = None if not resume_size else {"Range": f"bytes={resume_size}-"}
        params = {
            "Policy": ele.policy,
            "Key-Pair-Id": ele.keypair,
            "Signature": ele.signature,
        }
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"

        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common.alt_attempt_get(item).get()}/{get_download_retries()}] Downloading media with url  {ele.mpd}"
        )

        async with c.requests_async(
            url=url, headers=headers, params=params, forced=constants.getattr("DOWNLOAD_FORCE_KEY"),
             sign=True
        ) as l:
            item["total"] = item["total"] or int(l.headers.get("content-length"))
            total = item["total"]
            await common.batch_total_change_helper(None, total)
            data={
                        "content-total": total,
                        "content-type": l.headers.get("content-type"),
            }

            common_globals.log.debug(f"{get_medialog(ele)} data from request {data}")
            common_globals.log.debug(f"{get_medialog(ele)} total from request {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}")
            
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(
                    cache.set,
                    f"{item['name']}_headers",
                    data
                ),
            )
            temp_file_logger(placeholderObj, ele, common_globals.innerlog.get())
            if await check_forced_skip(ele, total) == 0:
                item["total"] = 0
                total = item["total"]
                await common.batch_total_change_helper(total, 0) if total else None
                return item

            elif total != resume_size:
                common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {common.alt_attempt_get(item).get()}/{get_download_retries()}] writing media to disk"
                )
                await download_fileobject_writer(total, l, ele, placeholderObj)
                common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {common.alt_attempt_get(item).get()}/{get_download_retries()}] finished writing media to disk"
                )
        await size_checker(placeholderObj.tempfilepath, ele, total)
        return item
    except Exception as E:
        await common.batch_total_change_helper(total, 0) if total else None
        raise E


async def download_fileobject_writer(total, l, ele, placeholderObj):
    pathstr = str(placeholderObj.tempfilepath)
    try:
        count = 1
        await common.send_msg(
            partial(
                progress_utils.add_download_job_multi_task,
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                ele.id,
                total=total,
            )
        )
        fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
        download_sleep = constants.getattr("DOWNLOAD_SLEEP")
        await common.send_msg(
            partial(progress_utils.update_download_multi_job_task, ele.id, visible=True)
        )
        chunk_size = get_ideal_chunk_size(total, placeholderObj.tempfilepath)

        update_count = get_update_count(total, placeholderObj.tempfilepath, chunk_size)

        async for chunk in l.iter_chunked(chunk_size):
            send_chunk_msg(ele,total,placeholderObj)
            await fileobject.write(chunk)
            await send_bar_msg_batch(
                        partial(
                            progress_utils.update_download_multi_job_task,
                            ele.id,
                            completed=pathlib.Path(placeholderObj.tempfilepath)
                            .absolute()
                            .stat()
                            .st_size,
                        ),count,update_count
            )
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
            await common.send_msg(
                partial(progress_utils.remove_download_multi_job_task, ele.id)
            )
        except Exception:
            None
