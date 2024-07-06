import asyncio
import pathlib
import re
import traceback
from functools import partial

import aiofiles
from humanfriendly import format_size

import ofscraper.classes.placeholder as placeholder
import ofscraper.download.utils.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.system.system as system
from ofscraper.classes.download_retries import download_retry
from ofscraper.download.utils.alt.attempt import alt_attempt_get
from ofscraper.download.utils.alt.data import (
    fresh_data_handler_alt,
    resume_data_handler_alt,
)
from ofscraper.download.utils.alt.item import (
    media_item_keys_alt,
    media_item_post_process_alt,
)
from ofscraper.download.utils.alt.params import get_alt_params
from ofscraper.download.utils.general import (
    check_forced_skip,
    downloadspace,
    get_medialog,
    size_checker,
)
from ofscraper.download.utils.handle_result import handle_result_alt
from ofscraper.download.utils.log import (
    get_url_log,
    path_to_file_logger,
    temp_file_logger,
)
from ofscraper.download.utils.progress.chunk import (
    get_ideal_chunk_size,
)
from ofscraper.download.utils.resume import get_resume_header, get_resume_size,resume_cleaner
from ofscraper.download.utils.retries import get_download_retries
from ofscraper.download.utils.send.chunk import send_chunk_msg
from ofscraper.download.utils.send.message import send_msg
from ofscraper.download.utils.total import batch_total_change_helper


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
                _attempt = alt_attempt_get(item)
                _attempt.set(_attempt.get(0) + 1)
                (
                    pathlib.Path(placeholderObj.tempfilepath).unlink(missing_ok=True)
                    if _attempt.get() > 1
                    else None
                )
                data = await asyncio.get_event_loop().run_in_executor(
                    common_globals.thread,
                    partial(cache.get, f"{item['name']}_{ele.username}_headers"),
                )
                status = False
                if data:
                    item, status = await resume_data_handler_alt(
                        data, item, ele, placeholderObj, batch=True
                    )
                else:
                    item, status = await fresh_data_handler_alt(
                        item, ele, placeholderObj
                    )
                # if out is null run request
                if not status:
                    try:
                        item = await alt_download_sendreq(item, c, ele, placeholderObj)
                    except Exception as E:
                        raise E
                return item
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


async def alt_download_sendreq(item, c, ele, placeholderObj):
    _attempt = alt_attempt_get(item)
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
    try:
        resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
        headers = get_resume_header(resume_size, item["total"])
        common_globals.log.debug(f"{get_medialog(ele)} resume header {headers}")
        params = get_alt_params(ele)
        base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
        url = f"{base_url}{item['origname']}"

        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {alt_attempt_get(item).get()}/{get_download_retries()}] Downloading media with url  {ele.mpd}"
        )

        async with c.requests_async(
            url=url,
            headers=headers,
            params=params,
            forced=constants.getattr("DOWNLOAD_FORCE_KEY"),
        ) as l:
            item["total"] = int(l.headers.get("content-length"))
            total = item["total"]
            await batch_total_change_helper(None, total)
            data = {
                "content-total": total,
                "content-type": l.headers.get("content-type"),
            }

            common_globals.log.debug(f"{get_medialog(ele)} data from request {data}")
            common_globals.log.debug(
                f"{get_medialog(ele)} total from request {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
            )

            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(cache.set, f"{item['name']}_{ele.username}_headers", data),
            )
            temp_file_logger(placeholderObj, ele, common_globals.innerlog.get())
            if await check_forced_skip(ele, total) == 0:
                item["total"] = 0
                total = item["total"]
                await batch_total_change_helper(total, 0) if total else None
                return item

            elif total != resume_size:
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {alt_attempt_get(item).get()}/{get_download_retries()}] writing media to disk"
                )
                resume_cleaner(resume_size,total,placeholderObj.tempfilepath)
                await download_fileobject_writer(total, l, ele, placeholderObj)
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {alt_attempt_get(item).get()}/{get_download_retries()}] finished writing media to disk"
                )
        await size_checker(placeholderObj.tempfilepath, ele, total)
        return item
    except Exception as E:
        await batch_total_change_helper(total, 0) if total else None
        raise E



async def download_fileobject_writer(total, l, ele, placeholderObj):
    if total > constants.getattr("MAX_READ_SIZE"):
        await download_fileobject_writer_streamer(total, l, ele, placeholderObj)
    else:
        await download_fileobject_writer_reader(ele,total, l, placeholderObj)



async def download_fileobject_writer_reader(ele,total, res, placeholderObj):
    pathstr = str(placeholderObj.tempfilepath)
    await send_msg(
            partial(
                progress_updater.add_download_job_multi_task,
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                ele.id,
                total=total,
                file=placeholderObj.tempfilepath,
            )
    )
    fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
    try:
        await fileobject.write(await res.read_())
    except Exception as E:
        raise E
    finally:
        # Close file if needed
        try:
            await fileobject.close()
        except Exception:
            None
        try:
            await send_msg(
                partial(progress_updater.remove_download_multi_job_task, ele.id)
            )
        except Exception:
            None

async def download_fileobject_writer_streamer(total, req, ele, placeholderObj):
    pathstr = str(placeholderObj.tempfilepath)
    try:
        await send_msg(
            partial(
                progress_updater.add_download_job_multi_task,
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                ele.id,
                total=total,
                file=placeholderObj.tempfilepath,
            )
        )
        fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
        download_sleep = constants.getattr("DOWNLOAD_SLEEP")
        chunk_size = get_ideal_chunk_size(total, placeholderObj.tempfilepath)

        async for chunk in req.iter_chunked(chunk_size):
            await fileobject.write(chunk)
            send_chunk_msg(ele, total, placeholderObj)
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
            await send_msg(
                partial(progress_updater.remove_download_multi_job_task, ele.id)
            )
        except Exception:
            None
