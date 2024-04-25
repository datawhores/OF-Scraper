import asyncio
import pathlib
import re
import traceback
from functools import partial

import aiofiles

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.classes.placeholder as placeholder
import ofscraper.download.shared.common.general as common
import ofscraper.download.shared.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.system.system as system
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


async def alt_download(c, ele, username, model_id):
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} Downloading with batch protected media downloader"
    )
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
    )
    async for _ in download_retry():
        with _:
            sharedPlaceholderObj = await placeholder.Placeholders(ele, "mp4").init()
            audio, video = await ele.mpd_dict
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
                    common_globals.cache_thread,
                    partial(cache.get, f"{item['name']}_headers"),
                )
                if data:
                    return await main_data_handler(data, item, c, ele, placeholderObj)
                else:
                    return await alt_data_handler(item, c, ele, placeholderObj)
            except OSError as E:
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Number of unique open files across all processes-> {len(system.getOpenFiles())}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}"
                )
                raise E
            except Exception as E:
                common_globals.innerlog.get().traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] {traceback.format_exc()}"
                )
                common_globals.innerlog.get().traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] {E}"
                )
                raise E


async def main_data_handler(data, item, c, ele, placeholderObj):
    item["total"] = int(data.get("content-length"))
    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    if await check_forced_skip(ele, item["total"]) == 0:
        item["total"] = 0
        return item
    elif item["total"] == resume_size:
        return item
    elif item["total"] != resume_size:
        return await alt_download_sendreq(item, c, ele, placeholderObj)


async def alt_data_handler(item, c, ele, placeholderObj):
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
        f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}] download temp path {placeholderObj.tempfilepath}"
    )
    item["total"] = item["total"] if _attempt.get() == 1 else None

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
        return await send_req_inner(c, ele, item, placeholderObj)
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, item, placeholderObj):
    old_total = item["total"]
    total = old_total
    try:
        await common.batch_total_change_helper(None, total)
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
            temp_file_logger(placeholderObj, ele, common_globals.innerlog.get())
            if await check_forced_skip(ele, new_total) == 0:
                item["total"] = 0
                await common.batch_total_change_helper(old_total, 0)
                return item
            elif total != resume_size:
                item["total"] = new_total
                total = new_total
                await common.batch_total_change_helper(old_total, total)
                await download_fileobject_writer(total, l, ele, placeholderObj)
        await size_checker(placeholderObj.tempfilepath, ele, item["total"])
        return item
    except Exception as E:
        await common.batch_total_change_helper(None, -(total or 0))
        raise E


async def download_fileobject_writer(total, l, ele, placeholderObj):
    pathstr = str(placeholderObj.tempfilepath)
    try:
        count = 0
        await common.send_msg(
            {
                "type": "add_task",
                "args": (
                    f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                    ele.id,
                ),
                "total": total,
                "visible": False,
            }
        )
        fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
        download_sleep = constants.getattr("DOWNLOAD_SLEEP")
        await common.send_msg({"type": "update", "args": (ele.id,), "visible": True})

        async for chunk in l.iter_chunked(constants.getattr("maxChunkSizeB")):
            count = count + 1
            common_globals.innerlog.get().trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(placeholderObj.tempfilepath).absolute().stat().st_size)}/{total}"
            )
            await fileobject.write(chunk)
            if count == constants.getattr("CHUNK_ITER"):
                await common.send_msg(
                    {
                        "type": "update",
                        "args": (ele.id,),
                        "completed": (
                            pathlib.Path(placeholderObj.tempfilepath)
                            .absolute()
                            .stat()
                            .st_size
                        ),
                    }
                )
                count = 0
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
            await common.send_msg({"type": "remove_task", "args": (ele.id,)})
        except Exception:
            None
