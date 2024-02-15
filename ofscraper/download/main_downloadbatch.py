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
import ofscraper.download.common as common
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.paths.paths as paths
from ofscraper.download.common import (
    addLocalDir,
    check_forced_skip,
    downloadspace,
    get_medialog,
    get_url_log,
    metadata,
    moveHelper,
    path_to_file_logger,
    sem_wrapper,
    set_profile_cache_helper,
    set_time,
    size_checker,
)
from ofscraper.utils.context.run_async import run


async def main_download(c, ele, username, model_id):
    common.innerlog.get().debug(
        f"{get_medialog(ele)} Downloading with normal batch downloader"
    )
    common.innerlog.get().debug(f"{get_medialog(ele)} download url: {get_url_log(ele)}")
    if read_args.retriveArgs().metadata != None:
        return await metadata(
            c,
            ele,
            username,
            model_id,
        )

    result = list(await main_download_downloader(c, ele, username, model_id))
    if result[0] == 0:
        if ele.mediatype != "forced_skipped":
            await operations.update_media_table(
                ele,
                filename=None,
                model_id=model_id,
                username=username,
                downloaded=True,
            )
        return ele.mediatype, 0
    total, temp_path, path_to_file = result
    await size_checker(temp_path, ele, total, path_to_file)
    common.innerlog.get().debug(
        f"{get_medialog(ele)} {ele.final_filename} size match target: {total} vs actual: {pathlib.Path(temp_path).absolute().stat().st_size}"
    )
    common.innerlog.get().debug(
        f"{get_medialog(ele)} renaming {pathlib.Path(temp_path).absolute()} -> {path_to_file}"
    )
    moveHelper(temp_path, path_to_file, ele, common.innerlog.get())
    addLocalDir(placeholder.Placeholders().getmediadir(ele, username, model_id))

    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        common.innerlog.get().debug(
            f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
        )
        set_time(path_to_file, newDate)
        common.innerlog.get().debug(
            f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )
    if ele.id:
        await operations.update_media_table(
            ele,
            filename=path_to_file,
            model_id=model_id,
            username=username,
            downloaded=True,
        )
    await set_profile_cache_helper(ele)
    return ele.mediatype, total


async def main_download_downloader(c, ele, username, model_id):
    try:
        async for _ in AsyncRetrying(
            stop=stop_after_attempt(constants.getattr("DOWNLOAD_RETRIES")),
            wait=wait_random(
                min=constants.getattr("OF_MIN"), max=constants.getattr("OF_MAX")
            ),
            reraise=True,
        ):
            with _:
                placeholderObj = placeholder.Placeholders()
                placeholderObj.getDirs(ele, username, model_id)
                placeholderObj.tempfilename = f"{ele.final_filename}_{ele.id}.part"
                data = await asyncio.get_event_loop().run_in_executor(
                    common.cache_thread,
                    partial(cache.get, f"{ele.id}_headers"),
                )
                if data and data.get("content-length"):
                    content_type = data.get("content-type").split("/")[-1]
                    total = int(data.get("content-length"))
                    placeholderObj.createfilename(ele, username, model_id, content_type)
                    placeholderObj.set_final_path()
                    resume_size = (
                        0
                        if not pathlib.Path(placeholderObj.tempfilename).exists()
                        else pathlib.Path(placeholderObj.tempfilename)
                        .absolute()
                        .stat()
                        .st_size
                    )
                    if await check_forced_skip(ele, total) == 0:
                        return [0]
                    elif total == resume_size:
                        path_to_file_logger(placeholderObj, ele, common.innerlog.get())
                        return (
                            total,
                            placeholderObj.tempfilename,
                            placeholderObj.trunicated_filename,
                        )
                    elif total < resume_size:
                        pathlib.Path(placeholderObj.tempfilename).unlink(
                            missing_ok=True
                        )
                else:
                    paths.truncate(pathlib.Path(placeholderObj.tempfilename)).unlink(
                        missing_ok=True
                    )
    except Exception as E:
        raise E
    common.attempt.set(0)
    try:
        async for _ in AsyncRetrying(
            stop=stop_after_attempt(constants.getattr("DOWNLOAD_RETRIES")),
            wait=wait_random(
                min=constants.getattr("OF_MIN"), max=constants.getattr("OF_MAX")
            ),
            reraise=True,
            retry=retry_if_not_exception_message(
                constants.getattr("SPACE_DOWNLOAD_MESSAGE")
            ),
        ):
            with _:
                try:
                    total = int(data.get("content-length")) if data else None
                    return await main_download_sendreq(
                        c, ele, placeholderObj, username, model_id, total
                    )
                except Exception as E:
                    raise E
    except Exception as E:
        raise E


async def main_download_sendreq(c, ele, placeholderObj, username, model_id, total):
    downloadspace()
    common.attempt.set(common.attempt.get(0) + 1)
    total = total if common.attempt.get() == 1 else None
    try:
        common.innerlog.get().debug(
            f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] download temp path {placeholderObj.tempfilename}"
        )
        if not total:
            placeholderObj.tempfilename.unlink(missing_ok=True)
        resume_size = (
            0
            if not pathlib.Path(placeholderObj.tempfilename).exists()
            else pathlib.Path(placeholderObj.tempfilename).absolute().stat().st_size
        )
        if not total or total > resume_size:
            url = ele.url
            headers = (
                None if resume_size == 0 else {"Range": f"bytes={resume_size}-{total}"}
            )

            @sem_wrapper(common.req_sem)
            async def inner():
                async with c.requests(url=url, headers=headers)() as r:
                    if r.ok:
                        total = int(r.headers["content-length"])
                        await common.send_msg((None, 0, total))
                        content_type = r.headers.get("content-type").split("/")[-1]
                        if not content_type and ele.mediatype.lower() == "videos":
                            content_type = "mp4"
                        if not content_type and ele.mediatype.lower() == "images":
                            content_type = "jpg"
                        if not placeholderObj.filename:
                            placeholderObj.createfilename(
                                ele, username, model_id, content_type
                            )
                            placeholderObj.set_final_path()
                        path_to_file_logger(placeholderObj, ele, common.innerlog.get())
                        if await check_forced_skip(ele, total) == 0:
                            return [0]
                        elif total == resume_size:
                            return (
                                total,
                                placeholderObj.tempfilename,
                                placeholderObj.trunicated_filename,
                            )
                        elif total < resume_size:
                            placeholderObj.tempfilename.unlink(missing_ok=True)
                        await main_download_datahandler(r, ele, total, placeholderObj)
                        await asyncio.get_event_loop().run_in_executor(
                            common.cache_thread,
                            partial(
                                cache.set,
                                f"{ele.id}_headers",
                                {
                                    "content-length": r.headers.get("content-length"),
                                    "content-type": r.headers.get("content-type"),
                                },
                            ),
                        )
                        await size_checker(placeholderObj.tempfilename, ele, total)
                        return (
                            total,
                            placeholderObj.tempfilename,
                            placeholderObj.trunicated_filename,
                        )
                    else:
                        common.innerlog.get().debug(
                            f"[bold] {get_medialog(ele)} main download response status code [/bold]: {r.status}"
                        )
                        common.innerlog.get().debug(
                            f"[bold] {get_medialog(ele)} main download  response text [/bold]: {await r.text_()}"
                        )
                        common.innerlog.get().debug(
                            f"[bold] {get_medialog(ele)}main download headers [/bold]: {r.headers}"
                        )
                        r.raise_for_status()
                    await asyncio.get_event_loop().run_in_executor(
                        common.cache_thread,
                        partial(cache.touch, f"{ele.filename}_headers", 1),
                    )

            return await inner()
        await size_checker(placeholderObj.tempfilename, ele, total)
        return placeholderObj.tempfilename, placeholderObj.trunicated_filename
    except OSError as E:
        common.innerlog.get().traceback_(E)
        common.innerlog.get().traceback_(traceback.format_exc())
        common.innerlog.get().debug(
            f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}"
        )
        common.innerlog.get().debug(
            f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of unique open files across all processes-> {len(system.getOpenFiles())}"
        )
        common.innerlog.get().debug(
            f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}"
        )
    except Exception as E:
        common.innerlog.get().traceback_(
            f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {traceback.format_exc()}"
        )
        common.innerlog.get().traceback_(
            f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {E}"
        )
        raise E


@sem_wrapper
async def main_download_datahandler(r, ele, total, placeholderObj):
    pathstr = str(placeholderObj.trunicated_filename)
    downloadprogress = (
        config_data.get_show_downloadprogress() or read_args.retriveArgs().downloadbars
    )
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

        fileobject = await aiofiles.open(placeholderObj.tempfilename, "ab").__aenter__()
        await common.send_msg({"type": "update", "args": (ele.id,), "visible": True})
        async for chunk in r.iter_chunked(constants.getattr("maxChunkSizeB")):
            count = count + 1
            if downloadprogress:
                count = count + 1
            common.innerlog.get().trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(placeholderObj.tempfilename).absolute().stat().st_size)}/{total}"
            )
            await fileobject.write(chunk)
            if count == constants.getattr("CHUNK_ITER"):
                await common.send_msg(
                    {
                        "type": "update",
                        "args": (ele.id,),
                        "completed": (
                            pathlib.Path(placeholderObj.tempfilename)
                            .absolute()
                            .stat()
                            .st_size
                        ),
                    }
                )
                count = 0
    except Exception as E:
        # reset download data
        await common.send_msg((None, 0, -total))
        raise E
    finally:
        try:
            await common.send_msg({"type": "remove_task", "args": (ele.id,)})
        except:
            None

        try:
            await fileobject.close()
        except Exception:
            None
