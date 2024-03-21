import asyncio
import pathlib
import re
import subprocess
import traceback
from functools import partial

import aiofiles
import arrow
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_message,
    stop_after_attempt,
    wait_random,
)

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.common.common as common
import ofscraper.download.common.globals as common_globals
import ofscraper.download.common.keyhelpers as keyhelpers
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.settings as settings
from ofscraper.download.common.common import (
    addLocalDir,
    check_forced_skip,
    downloadspace,
    get_item_total,
    get_medialog,
    get_resume_size,
    get_url_log,
    metadata,
    moveHelper,
    path_to_file_logger,
    sem_wrapper,
    set_time,
    size_checker,
    temp_file_logger,
)
from ofscraper.utils.context.run_async import run


async def alt_download(c, ele, username, model_id):
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} Downloading with batch protected media downloader"
    )
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
    )
    sharedPlaceholderObj = placeholder.Placeholders(ele, "mp4")
    await sharedPlaceholderObj.init()
    if read_args.retriveArgs().metadata != None:
        return await metadata(
            c, ele, username, model_id, placeholderObj=sharedPlaceholderObj
        )
    audio, video = await ele.mpd_dict
    path_to_file_logger(sharedPlaceholderObj, ele, common_globals.innerlog.get())
    audio = await alt_download_downloader(audio, c, ele)
    video = await alt_download_downloader(video, c, ele)

    post_result = await media_item_post_process(audio, video, ele, username, model_id)
    if post_result:
        return post_result
    await media_item_keys(c, audio, video, ele)
    return await handle_result(
        sharedPlaceholderObj, ele, audio, video, username, model_id
    )


async def handle_result(sharedPlaceholderObj, ele, audio, video, username, model_id):
    tempPlaceholder = placeholder.tempFilePlaceholder(
        ele, f"temp_{ele.id or await ele.final_filename}.mp4"
    )
    await tempPlaceholder.init()
    temp_path = tempPlaceholder.tempfilepath

    temp_path.unlink(missing_ok=True)
    t = subprocess.run(
        [
            settings.get_ffmpeg(),
            "-i",
            str(video["path"]),
            "-i",
            str(audio["path"]),
            "-c",
            "copy",
            "-movflags",
            "use_metadata_tags",
            str(temp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if t.stderr.decode().find("Output") == -1:
        common_globals.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg failed")
        common_globals.innerlog.get().debug(
            f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}"
        )
        common_globals.innerlog.get().debug(
            f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}"
        )
    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    common_globals.innerlog.get().debug(
        f"Moving intermediate path {temp_path} to {sharedPlaceholderObj.trunicated_filepath}"
    )
    moveHelper(
        temp_path,
        sharedPlaceholderObj.trunicated_filepath,
        ele,
        common_globals.innerlog.get(),
    )
    addLocalDir(sharedPlaceholderObj.trunicated_filepath)
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        set_time(sharedPlaceholderObj.trunicated_filepath, newDate)
        common_globals.innerlog.get().debug(
            f"{get_medialog(ele)} Date set to {arrow.get(sharedPlaceholderObj.trunicated_filepath.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )
    if ele.id:
        await operations.update_media_table(
            ele,
            filename=sharedPlaceholderObj.trunicated_filepath,
            model_id=model_id,
            username=username,
            downloaded=True,
            hash=await common.get_hash(sharedPlaceholderObj, mediatype=ele.mediatype),
        )
    return ele.mediatype, video["total"] + audio["total"]


async def media_item_post_process(audio, video, ele, username, model_id):
    if (audio["total"] + video["total"]) == 0:
        if ele.mediatype != "forced_skipped":
            await operations.update_media_table(
                ele,
                filename=None,
                model_id=model_id,
                username=username,
                downloaded=True,
            )
        return ele.mediatype, 0
    for m in [audio, video]:
        m["total"] = get_item_total(m)

    for m in [audio, video]:
        if not isinstance(m, dict):
            return m
        await size_checker(m["path"], ele, m["total"])


async def media_item_keys(c, audio, video, ele):
    for item in [audio, video]:
        item = await keyhelpers.un_encrypt(item, c, ele, common_globals.innerlog.get())


async def alt_download_downloader(
    item,
    c,
    ele,
):
    downloadspace(mediatype=ele.mediatype)
    placeholderObj = placeholder.tempFilePlaceholder(ele, f"{item['name']}.part")
    await placeholderObj.init()
    item["path"] = placeholderObj.tempfilepath

    async for _ in AsyncRetrying(
        stop=stop_after_attempt(constants.getattr("DOWNLOAD_RETRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"), max=constants.getattr("OF_MAX")
        ),
        retry=retry_if_not_exception_message(
            constants.getattr("SPACE_DOWNLOAD_MESSAGE")
        ),
        reraise=True,
    ):
        with _:
            try:
                _attempt = common.alt_attempt_get(item)
                _attempt.set(_attempt.get(0) + 1)
                pathlib.Path(placeholderObj.tempfilepath).unlink(
                    missing_ok=True
                ) if _attempt.get() > 1 else None
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
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of unique open files across all processes-> {len(system.getOpenFiles())}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}"
                )
                raise E
            except Exception as E:
                common_globals.innerlog.get().traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {traceback.format_exc()}"
                )
                common_globals.innerlog.get().traceback_(
                    f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {E}"
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
        f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] download temp path {placeholderObj.tempfilepath}"
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
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] download temp path {placeholderObj.tempfilepath}"
        )
        return await send_req_inner(c, ele, item, placeholderObj)
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, item, placeholderObj):
    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    total = item["total"]
    await common.send_msg((None, 0, total)) if total else None
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
    await common.send_msg((None, 0, total)) if total else None
    async with sem_wrapper(common_globals.req_sem):
        async with c.requests(url=url, headers=headers, params=params)() as l:
            if l.ok:
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
                await common.send_msg((None, 0, new_total)) if not total else None
                temp_file_logger(placeholderObj, ele, common_globals.innerlog.get())
                item["total"] = new_total
                total = item["total"]
                if await check_forced_skip(ele, total) == 0:
                    item["total"] = 0
                    return item
                elif total == resume_size:
                    None
                else:
                    await download_fileobject_writerr(total, l, ele, placeholderObj)

            else:
                common_globals.innerlog.get().debug(
                    f"[bold]  {get_medialog(ele)}  main download data finder status[/bold]: {l.status}"
                )
                common_globals.innerlog.get().debug(
                    f"[bold] {get_medialog(ele)}  main download data finder text [/bold]: {await l.text_()}"
                )
                common_globals.innerlog.get().debug(
                    f"[bold]  {get_medialog(ele)} main download data finder headers [/bold]: {l.headers}"
                )
                l.raise_for_status()

    await size_checker(placeholderObj.tempfilepath, ele, total)
    return item


async def download_fileobject_writerr(total, l, ele, placeholderObj):
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
        # reset download data
        await common.send_msg((None, 0, -total))
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
