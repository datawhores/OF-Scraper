"""
                                                             
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
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.download.common.common import (
    addLocalDir,
    check_forced_skip,
    downloadspace,
    get_data,
    get_medialog,
    get_resume_size,
    get_unknown_content_type,
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
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} Downloading with normal batch downloader"
    )
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} download url: {get_url_log(ele)}"
    )
    if read_args.retriveArgs().metadata != None:
        return await metadata(
            c,
            ele,
            username,
            model_id,
        )

    result = list(await main_download_downloader(c, ele))
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
    return await handle_result(result, ele, username, model_id)


async def handle_result(result, ele, username, model_id):
    total, temp_path, placeholderObj = result
    path_to_file = placeholderObj.trunicated_filepath
    await size_checker(temp_path, ele, total, path_to_file)
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} { await ele.final_filename} size match target: {total} vs actual: {pathlib.Path(temp_path).absolute().stat().st_size}"
    )
    common_globals.innerlog.get().debug(
        f"{get_medialog(ele)} renaming {pathlib.Path(temp_path).absolute()} -> {path_to_file}"
    )
    moveHelper(temp_path, path_to_file, ele, common_globals.innerlog.get())
    addLocalDir(placeholderObj.filedir)
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        common_globals.innerlog.get().debug(
            f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
        )
        set_time(path_to_file, newDate)
        common_globals.innerlog.get().debug(
            f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )
    if ele.id:
        await operations.update_media_table(
            ele,
            filename=path_to_file,
            model_id=model_id,
            username=username,
            downloaded=True,
            hash=await common.get_hash(path_to_file, mediatype=ele.mediatype),
        )
    await set_profile_cache_helper(ele)
    return ele.mediatype, total


async def main_download_downloader(c, ele):
    downloadspace(mediatype=ele.mediatype)
    tempholderObj = placeholder.tempFilePlaceholder(
        ele, f"{await ele.final_filename}_{ele.id}.part"
    )
    await tempholderObj.init()
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
                common_globals.attempt.set(common_globals.attempt.get(0) + 1)
                pathlib.Path(tempholderObj.tempfilepath).unlink(
                    missing_ok=True
                ) if common_globals.attempt.get() > 1 else None
                data = await get_data(ele)
                if data:
                    return await main_data_handler(data, c, ele, tempholderObj)
                else:
                    return await alt_data_handler(c, ele, tempholderObj)

            except OSError as E:
                common_globals.innerlog.get().debug(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}"
                )
                common_globals.innerlog.get().debug(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of unique open files across all processes-> {len(system.getOpenFiles())}"
                )
                common_globals.innerlog.get().debug(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}"
                )
                raise E
            except Exception as E:
                common_globals.innerlog.get().traceback_(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {traceback.format_exc()}"
                )
                common_globals.innerlog.get().traceback_(
                    f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {E}"
                )
                raise E


async def alt_data_handler(c, ele, tempholderObj):
    result = None
    try:
        result = await main_download_sendreq(
            c, ele, tempholderObj, placeholderObj=None, total=None
        )
    except Exception as E:
        raise E
    return result


async def main_data_handler(data, c, ele, tempholderObj):
    content_type = data.get("content-type").split("/")[-1]
    total = int(data.get("content-length"))
    placeholderObj = placeholder.Placeholders(ele, content_type)
    resume_size = get_resume_size(tempholderObj, mediatype=ele.mediatype)
    await placeholderObj.init()
    # other
    if await check_forced_skip(ele, total) == 0:
        path_to_file_logger(placeholderObj, ele, common_globals.innerlog.get())
        return [0]
    elif total == resume_size:
        path_to_file_logger(placeholderObj, ele, common_globals.innerlog.get())
        return (
            total,
            tempholderObj.tempfilepath,
            placeholderObj,
        )

    else:
        try:
            return await main_download_sendreq(
                c, ele, tempholderObj, total=total, placeholderObj=placeholderObj
            )
        except Exception as E:
            raise E


async def main_download_sendreq(c, ele, tempholderObj, placeholderObj=None, total=None):
    try:
        common_globals.innerlog.get().debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] download temp path {tempholderObj.tempfilepath}"
        )
        total = total if common_globals.attempt.get() == 1 else None
        return await send_req_inner(
            c, ele, tempholderObj, placeholderObj=placeholderObj, total=total
        )
    except OSError as E:
        raise E
    except Exception as E:
        raise E


async def send_req_inner(c, ele, tempholderObj, placeholderObj=None, total=None):
    resume_size = get_resume_size(tempholderObj, mediatype=ele.mediatype)
    headers = (
        None
        if resume_size == 0 or not total
        else {"Range": f"bytes={resume_size}-{total}"}
    )
    await common.send_msg((None, 0, total)) if total else None
    async with sem_wrapper(common_globals.req_sem):
        async with c.requests(url=ele.url, headers=headers)() as r:
            if r.ok:
                await asyncio.get_event_loop().run_in_executor(
                    common_globals.cache_thread,
                    partial(
                        cache.set,
                        f"{ele.id}_headers",
                        {
                            "content-length": r.headers.get("content-length"),
                            "content-type": r.headers.get("content-type"),
                        },
                    ),
                )
                new_total = int(r.headers["content-length"])
                await common.send_msg((None, 0, new_total)) if not total else None
                total = new_total
                content_type = r.headers.get("content-type").split("/")[-1]
                content_type = get_unknown_content_type(ele)
                if not placeholderObj:
                    placeholderObj = placeholder.Placeholders(ele, content_type)
                    await placeholderObj.init()
                path_to_file_logger(placeholderObj, ele, common_globals.innerlog.get())
                if await check_forced_skip(ele, total) == 0:
                    total = 0
                elif total == resume_size:
                    None
                else:
                    await download_fileobject_writer(
                        r, ele, total, tempholderObj, placeholderObj
                    )
            else:
                common_globals.innerlog.get().debug(
                    f"[bold] {get_medialog(ele)} main download response status code [/bold]: {r.status}"
                )
                common_globals.innerlog.get().debug(
                    f"[bold] {get_medialog(ele)} main download  response text [/bold]: {await r.text_()}"
                )
                common_globals.innerlog.get().debug(
                    f"[bold] {get_medialog(ele)}main download headers [/bold]: {r.headers}"
                )
                r.raise_for_status()

    await size_checker(tempholderObj.tempfilepath, ele, total)
    return (total, tempholderObj.tempfilepath, placeholderObj)


async def download_fileobject_writer(r, ele, total, tempholderObj, placeholderObj):
    pathstr = str(placeholderObj.trunicated_filepath)
    downloadprogress = settings.get_download_bars()
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

        fileobject = await aiofiles.open(tempholderObj.tempfilepath, "ab").__aenter__()
        download_sleep = constants.getattr("DOWNLOAD_SLEEP")

        await common.send_msg({"type": "update", "args": (ele.id,), "visible": True})
        async for chunk in r.iter_chunked(constants.getattr("maxChunkSizeB")):
            count = count + 1
            if downloadprogress:
                count = count + 1
            common_globals.innerlog.get().trace(
                f"{get_medialog(ele)} Download Progress:{(pathlib.Path(tempholderObj.tempfilepath).absolute().stat().st_size)}/{total}"
            )
            await fileobject.write(chunk)
            if count == constants.getattr("CHUNK_ITER"):
                await common.send_msg(
                    {
                        "type": "update",
                        "args": (ele.id,),
                        "completed": (
                            pathlib.Path(tempholderObj.tempfilepath)
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
        try:
            await common.send_msg({"type": "remove_task", "args": (ele.id,)})
        except:
            None

        try:
            await fileobject.close()
        except Exception:
            None
