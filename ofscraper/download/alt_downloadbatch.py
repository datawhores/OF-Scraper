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
import ofscraper.download.common as common
import ofscraper.download.keyhelpers as keyhelpers
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
    get_item_total,
    get_medialog,
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
    downloadspace()
    common.innerlog.get().debug(
        f"{get_medialog(ele)} Downloading with batch protected media downloader"
    )
    common.innerlog.get().debug(
        f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
    )
    if read_args.retriveArgs().metadata != None:
        sharedPlaceholderObj = placeholder.Placeholders()
        sharedPlaceholderObj.getmediadir(ele, username, model_id, create=False)
        sharedPlaceholderObj.createfilename(ele, username, model_id, "mp4")
        sharedPlaceholderObj.set_final_path()
        return await metadata(
            c, ele, username, model_id, placeholderObj=sharedPlaceholderObj
        )
    audio, video = await ele.mpd_dict
    sharedPlaceholderObj = placeholder.Placeholders()
    sharedPlaceholderObj.getDirs(ele, username, model_id)
    sharedPlaceholderObj.createfilename(ele, username, model_id, "mp4")
    sharedPlaceholderObj.set_final_path()
    path_to_file_logger(sharedPlaceholderObj, ele, common.innerlog.get())

    audio = await alt_download_downloader(audio, c, ele, username, model_id)
    video = await alt_download_downloader(video, c, ele, username, model_id)

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
    for item in [audio, video]:
        item = await keyhelpers.un_encrypt(item, c, ele, common.innerlog.get())
    temp_path = paths.truncate(
        pathlib.Path(
            sharedPlaceholderObj.tempdir, f"temp_{ele.id or ele.final_filename}.mp4"
        )
    )
    temp_path.unlink(missing_ok=True)
    t = subprocess.run(
        [
            config_data.get_ffmpeg(),
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
        common.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg failed")
        common.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        common.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")
    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    common.innerlog.get().debug(
        f"Moving intermediate path {temp_path} to {sharedPlaceholderObj.trunicated_filename}"
    )
    moveHelper(
        temp_path, sharedPlaceholderObj.trunicated_filename, ele, common.innerlog.get()
    )
    addLocalDir(sharedPlaceholderObj.trunicated_filename)
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        set_time(sharedPlaceholderObj.trunicated_filename, newDate)
        common.innerlog.get().debug(
            f"{get_medialog(ele)} Date set to {arrow.get(sharedPlaceholderObj.trunicated_filename.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )
    if ele.id:
        await operations.update_media_table(
            ele,
            filename=sharedPlaceholderObj.trunicated_filename,
            model_id=model_id,
            username=username,
            downloaded=True,
        )
    return ele.mediatype, video["total"] + audio["total"]


async def alt_download_sendreq(item, c, ele, placeholderObj):
    base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
    url = f"{base_url}{item['origname']}"
    common.innerlog.get().debug(
        f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
    )

    _attempt = common.alt_attempt_get(item)
    _attempt.set(_attempt.get(0) + 1)
    item["total"] = item["total"] if _attempt.get() == 1 else None

    try:
        total = item.get("total")
        if total == None:
            placeholderObj.tempfilename.unlink(missing_ok=True)
        resume_size = (
            0
            if not pathlib.Path(placeholderObj.tempfilename).absolute().exists()
            else pathlib.Path(placeholderObj.tempfilename).absolute().stat().st_size
        )

        if not total or total > resume_size:
            headers = (
                {"Range": f"bytes={resume_size}-{total}"}
                if pathlib.Path(placeholderObj.tempfilename).exists()
                else None
            )
            params = {
                "Policy": ele.policy,
                "Key-Pair-Id": ele.keypair,
                "Signature": ele.signature,
            }

            @sem_wrapper(common.req_sem)
            async def inner():
                async with c.requests(url=url, headers=headers, params=params)() as l:
                    if l.ok:
                        total = int(l.headers["content-length"])
                        await common.send_msg((None, 0, total))
                        temp_file_logger(placeholderObj, ele, common.innerlog.get())
                        if await check_forced_skip(ele, total) == 0:
                            item["total"] = 0
                            return item
                        common.innerlog.get().debug(
                            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] download temp path {placeholderObj.tempfilename}"
                        )
                        item["total"] = total
                        await alt_download_datahandler(
                            item, total, l, ele, placeholderObj
                        )
                        await asyncio.get_event_loop().run_in_executor(
                            common.cache_thread,
                            partial(
                                cache.set,
                                f"{item['name']}_headers",
                                {
                                    "content-length": l.headers.get("content-length"),
                                    "content-type": l.headers.get("content-type"),
                                },
                            ),
                        )
                        await size_checker(placeholderObj.tempfilename, ele, total)
                        return item

                    else:
                        common.innerlog.get().debug(
                            f"[bold]  {get_medialog(ele)}  main download data finder status[/bold]: {l.status}"
                        )
                        common.innerlog.get().debug(
                            f"[bold] {get_medialog(ele)}  main download data finder text [/bold]: {await l.text_()}"
                        )
                        common.innerlog.get().debug(
                            f"[bold]  {get_medialog(ele)} main download data finder headers [/bold]: {l.headers}"
                        )
                        l.raise_for_status()

            return await inner()
        await size_checker(placeholderObj.tempfilename, ele, total)
        return item

    except OSError as E:
        common.log.traceback_(E)
        common.log.traceback_(traceback.format_exc())
        common.log.debug(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}"
        )
        common.log.debug(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Number of unique open files across all processes-> {len(system.getOpenFiles())}"
        )
        common.log.debug(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}"
        )
    except Exception as E:
        common.innerlog.get().traceback_(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {traceback.format_exc()}"
        )
        common.innerlog.get().traceback_(
            f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}] {E}"
        )
        raise E


@sem_wrapper
async def alt_download_datahandler(item, total, l, ele, placeholderObj):
    pathstr = str(placeholderObj.tempfilename)
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

        async for chunk in l.iter_chunked(constants.getattr("maxChunkSizeB")):
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
        # Close file if needed
        try:
            await fileobject.close()
        except Exception:
            None

        try:
            await common.send_msg({"type": "remove_task", "args": (ele.id,)})
        except Exception:
            None


async def alt_download_downloader(item, c, ele, username, model_id):
    try:
        async for _ in AsyncRetrying(
            stop=stop_after_attempt(constants.getattr("DOWNLOAD_RETRIES")),
            wait=wait_random(
                min=constants.getattr("OF_MIN"), max=constants.getattr("OF_MAX")
            ),
            reraise=True,
        ):
            with _:
                common.attempt.set(common.attempt.get(0) + 1)
                placeholderObj = placeholder.Placeholders()
                placeholderObj.gettempDir(ele, username, model_id)
                placeholderObj.tempfilename = f"{item['name']}.part"
                item["path"] = placeholderObj.tempfilename
                data = await asyncio.get_event_loop().run_in_executor(
                    common.cache_thread,
                    partial(cache.get, f"{item['name']}_headers"),
                )
                if data:
                    item["total"] = int(data.get("content-length"))
                    resume_size = (
                        0
                        if not pathlib.Path(placeholderObj.tempfilename).exists()
                        else pathlib.Path(placeholderObj.tempfilename)
                        .absolute()
                        .stat()
                        .st_size
                    )
                    if await check_forced_skip(ele, item["total"]) == 0:
                        item["total"] = 0
                        return item
                    elif item["total"] == resume_size:
                        return item
                    elif item["total"] < resume_size:
                        pathlib.Path(placeholderObj.tempfilename).unlink(
                            missing_ok=True
                        )
                else:
                    placeholderObj.tempfilename.unlink(missing_ok=True)
    except Exception as E:
        raise E
    _attempt = common.alt_attempt_get(item)
    _attempt.set(0)
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
                    return await alt_download_sendreq(item, c, ele, placeholderObj)
                except Exception as E:
                    raise E
    except Exception as E:
        raise E
