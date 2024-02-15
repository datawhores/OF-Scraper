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
import contextvars
import math
import os
import pathlib
import platform
import re
import shutil
import threading
import traceback
from collections import abc
from concurrent.futures import ThreadPoolExecutor
from functools import partial, singledispatch

from humanfriendly import format_size

try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import aioprocessing
from rich.console import Group
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Column
from tenacity import AsyncRetrying, retry, stop_after_attempt, wait_random

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.models.selector as selector
import ofscraper.utils.args.read as read_args
import ofscraper.utils.args.write as write_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as config_data
import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system as system
from ofscraper.classes.multiprocessprogress import MultiprocessProgress as MultiProgress
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

attempt = contextvars.ContextVar("attempt", default=0)
attempt2 = contextvars.ContextVar("attempt2", default=0)
total_count = contextvars.ContextVar("total", default=0)
total_count2 = contextvars.ContextVar("total2", default=0)
innerlog = contextvars.ContextVar("innerlog")
localDirSet = None
req_sem = None


def reset_globals():
    # reset globals

    global total_bytes_downloaded
    total_bytes_downloaded = 0
    global total_bytes
    total_bytes = 0
    global photo_count
    photo_count = 0
    global video_count
    video_count = 0
    global audio_count
    audio_count = 0
    global skipped
    skipped = 0
    global forced_skipped
    forced_skipped = 0
    global data
    data = 0
    global total_data
    total_data = 0
    global desc
    desc = "Progress: ({p_count} photos, {v_count} videos, {a_count} audios, {forced_skipped} skipped, {skipped} failed || {sumcount}/{mediacount}||{data}/{total})"
    global count_lock
    count_lock = aioprocessing.AioLock()
    global chunk_lock
    chunk_lock = aioprocessing.AioLock()

    # global
    global thread
    thread = ThreadPoolExecutor(max_workers=config_data.get_download_semaphores() * 2)
    global sem
    sem = semaphoreDelayed(config_data.get_download_semaphores())
    global cache_thread
    cache_thread = ThreadPoolExecutor()
    global dirSet
    dirSet = set()
    global mpd_sem
    mpd_sem = semaphoreDelayed(config_data.get_download_semaphores())
    global lock
    lock = asyncio.Lock()
    global maxfile_sem
    maxfile_sem = semaphoreDelayed(constants.getattr("MAXFILE_SEMAPHORE"))
    global console
    console = console_.get_shared_console()
    global localDirSet
    localDirSet = set()
    global req_sem
    req_sem = semaphoreDelayed(
        min(
            constants.getattr("REQ_SEMAPHORE_MULTI"),
            config_data.get_download_semaphores()
            * constants.getattr("REQ_SEMAPHORE_MULTI"),
        )
    )


def get_medialog(ele):
    return f"Media:{ele.id} Post:{ele.postid}"


def process_split_globals(pipeCopy, logCopy):
    global pipe
    global log
    global pipe_lock
    global lock_pool
    pipe = pipeCopy
    log = logCopy
    pipe_lock = threading.Lock()
    lock_pool = ThreadPoolExecutor()


def set_send_msg():
    global send_msg_helper
    if platform.system() != "Windows":
        send_msg_helper = send_msg_unix
    else:
        send_msg_helper = send_msg_win


async def send_msg(msg):
    global send_msg_helper
    await send_msg_helper(msg)


async def send_msg_win(msg):
    global pipe
    global pipe_lock
    global lock_pool
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(lock_pool, pipe_lock.acquire)
    try:
        await pipe.coro_send(msg)
    finally:
        await loop.run_in_executor(lock_pool, pipe_lock.release)


async def send_msg_unix(msg):
    global pipe
    await pipe.coro_send(msg)


def subProcessVariableInit(dateDict, userList, pipeCopy, logCopy, argsCopy):
    reset_globals()
    write_args.setArgs(argsCopy)
    dates.setLogDate(dateDict)
    selector.set_ALL_SUBS_DICT(userList)
    process_split_globals(pipeCopy, logCopy)
    set_send_msg()


@singledispatch
def sem_wrapper(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return sem_wrapper(args[0])
    return sem_wrapper(**kwargs)


@sem_wrapper.register
def _(input_sem: semaphoreDelayed):
    return partial(sem_wrapper, input_sem=input_sem)


@sem_wrapper.register
def _(func: abc.Callable, input_sem: None | semaphoreDelayed = None):
    async def inner(*args, input_sem=input_sem, **kwargs):
        if input_sem == None:
            input_sem = sem
        await input_sem.acquire()
        try:
            return await func(*args, **kwargs)
        except Exception as E:
            raise E
        finally:
            input_sem.release()

    return inner


def setupProgressBar(multi=False):
    downloadprogress = (
        config_data.get_show_downloadprogress() or read_args.retriveArgs().downloadbars
    )
    if not multi:
        job_progress = Progress(
            TextColumn("{task.description}", table_column=Column(ratio=2)),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TransferSpeedColumn(),
            DownloadColumn(),
        )
    else:
        job_progress = MultiProgress(
            TextColumn("{task.description}", table_column=Column(ratio=2)),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TransferSpeedColumn(),
            DownloadColumn(),
        )
    overall_progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    )
    progress_group = Group(overall_progress, Panel(Group(job_progress, fit=True)))
    progress_group.renderables[1].height = (
        max(15, console_.get_shared_console().size[1] - 2) if downloadprogress else 0
    )
    return progress_group, overall_progress, job_progress


async def update_total(update):
    global total_data
    global lock
    async with lock:
        total_data += update


def get_url_log(ele):
    url = ele.url or ele.mpd
    url = re.sub("/\w{5}\w+", "/{hidden}", url)
    if ele.url:
        url = re.sub(ele.filename, "{hidden}", url)
    return url


async def size_checker(path, ele, total, name=None):
    name = name or ele.filename
    if not pathlib.Path(path).exists():
        s = f"{get_medialog(ele)} {path} was not created"
        raise Exception(s)
    elif total - pathlib.Path(path).absolute().stat().st_size > 500:
        s = f"{get_medialog(ele)} {name} size mixmatch target: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        await asyncio.get_event_loop().run_in_executor(
            cache_thread, partial(cache.set, f"{ele.id}_headers", None)
        )
        raise Exception(s)
    elif (total - pathlib.Path(path).absolute().stat().st_size) < 0:
        s = f"{get_medialog(ele)} {path} size mixmatch target item too large: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        await asyncio.get_event_loop().run_in_executor(
            cache_thread, partial(cache.set, f"{ele.id}_headers", None)
        )
        raise Exception(s)


def path_to_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or log
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.getattr('NUM_TRIES')}] filename from config {placeholderObj.filename}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.getattr('NUM_TRIES')}] full path from config {pathlib.Path(placeholderObj.mediadir,f'{placeholderObj.filename}')}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.getattr('NUM_TRIES')}] full path trunicated from config {placeholderObj.trunicated_filename}"
    )


def temp_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or log
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.getattr('NUM_TRIES')}] filename from config {placeholderObj.tempfilename}"
    )


async def check_forced_skip(ele, *args):
    total = sum(map(lambda x: int(x), args))
    if total == 0:
        return 0
    file_size_limit = (
        read_args.retriveArgs().size_max or config_data.get_filesize_limit()
    )
    file_size_min = read_args.retriveArgs().size_min or config_data.get_filesize_limit()
    if int(file_size_limit) > 0 and (int(total) > int(file_size_limit)):
        ele.mediatype = "forced_skipped"
        log.debug(f"{get_medialog(ele)} {format_size(total)} over size limit")
        return 0
    elif int(file_size_min) > 0 and (int(total) < int(file_size_min)):
        ele.mediatype = "forced_skipped"
        log.debug(f"{get_medialog(ele)} {format_size(total)} under size min")
        return 0


async def metadata(c, ele, username, model_id, placeholderObj=None):
    log.info(
        f"{get_medialog(ele)} skipping adding download to disk because metadata is on"
    )
    download_data = await asyncio.get_event_loop().run_in_executor(
        cache_thread, partial(cache.get, f"{ele.id}_headers")
    )
    for _ in range(2):
        if placeholderObj:
            if ele.id:
                await operations.update_media_table(
                    ele,
                    filename=placeholderObj.trunicated_filename,
                    model_id=model_id,
                    username=username,
                    downloaded=metadata_downloaded_helper(placeholderObj),
                )
            return (
                ele.mediatype
                if metadata_downloaded_helper(placeholderObj)
                else "forced_skipped",
                0,
            )
        elif download_data and download_data.get("content-type"):
            content_type = download_data.get("content-type").split("/")[-1]
            placeholderObj = placeholder.Placeholders()
            placeholderObj.getDirs(ele, username, model_id, create=False)
            placeholderObj.createfilename(ele, username, model_id, content_type)
            placeholderObj.set_final_path()
            if ele.id:
                await operations.update_media_table(
                    ele,
                    filename=placeholderObj.trunicated_filename,
                    model_id=model_id,
                    username=username,
                    downloaded=metadata_downloaded_helper(placeholderObj),
                )
            return (
                ele.mediatype
                if metadata_downloaded_helper(placeholderObj)
                else "forced_skipped",
                0,
            )
        elif _ == 1:
            break
        else:
            try:
                async for _ in AsyncRetrying(
                    stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
                    wait=wait_random(
                        min=constants.getattr("OF_MIN"), max=constants.getattr("OF_MAX")
                    ),
                    reraise=True,
                ):
                    with _:
                        try:
                            placeholderObj = await metadata_helper(
                                c, ele, username, model_id, placeholderObj
                            )
                        except Exception as E:
                            raise E
            except Exception as E:
                log.traceback_(f"{get_medialog(ele)} Could not get placeholderObj {E}")
                log.traceback_(
                    f"{get_medialog(ele)} Could not get placeholderObj {traceback.format_exc()}"
                )
                log.debug(f"{get_medialog(ele)} using a generic placeholderObj")
                placeholderObj = meta_data_placeholder(ele, username, model_id)


def metadata_downloaded_helper(placeholderObj):
    if read_args.retriveArgs().metadata == "none":
        return None

    elif read_args.retriveArgs().metadata == "complete":
        return 1
    elif pathlib.Path(placeholderObj.trunicated_filename).exists():
        return 1
    return 0


@sem_wrapper
async def metadata_helper(c, ele, username, model_id, placeholderObj=None):
    url = ele.url or ele.mpd

    params = (
        {
            "Policy": ele.policy,
            "Key-Pair-Id": ele.keypair,
            "Signature": ele.signature,
        }
        if ele.mpd
        else None
    )
    attempt.set(attempt.get(0) + 1)
    log.debug(
        f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}]  Getting data for metadata insert"
    )
    async with c.requests(url=url, headers=None, params=params)() as r:
        if r.ok:
            headers = r.headers
            await asyncio.get_event_loop().run_in_executor(
                cache_thread,
                partial(
                    cache.set,
                    f"{ele.id}_headers",
                    {
                        "content-length": headers.get("content-length"),
                        "content-type": headers.get("content-type"),
                    },
                ),
            )
            content_type = headers.get("content-type").split("/")[-1]
            if not content_type and ele.mediatype.lower() == "videos":
                content_type = "mp4"
            elif not content_type and ele.mediatype.lower() == "images":
                content_type = "jpg"
            placeholderObj = placeholderObj or placeholder.Placeholders()
            placeholderObj.getDirs(ele, username, model_id, create=False)
            placeholderObj.createfilename(ele, username, model_id, content_type)
            placeholderObj.set_final_path()
            return placeholderObj

        else:
            r.raise_for_status()


def meta_data_placeholder(ele, username, model_id):
    if ele.mediatype.lower() == "videos":
        content_type = "mp4"
    elif ele.mediatype.lower() == "images":
        content_type = "jpg"
    elif ele.mediatype.lower() == "audios":
        content_type = "mp3"
    placeholderObj = placeholder.Placeholders()
    placeholderObj.getDirs(ele, username, model_id, create=False)
    placeholderObj.createfilename(ele, username, model_id, content_type)
    placeholderObj.set_final_path()
    return placeholderObj


def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
        return "0 B"
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f"{round(num_bytes / 10**9, 2)} GB"
    return f"{round(num_bytes / 10 ** 6, 2)} MB"


def set_time(path, timestamp):
    if platform.system() == "Windows":
        setctime(path, timestamp)
    pathlib.os.utime(path, (timestamp, timestamp))


def get_error_message(content):
    error_content = content.get("error", "No error message available")
    try:
        return error_content.get("message", "No error message available")
    except AttributeError:
        return error_content


async def set_profile_cache_helper(ele):
    if ele.postid and ele.responsetype == "profile":
        await asyncio.get_event_loop().run_in_executor(
            cache_thread, partial(cache.set, ele.postid, True)
        )


def moveHelper(temp, path_to_file, ele, log_=None):
    if not path_to_file.exists():
        shutil.move(temp, path_to_file)
    elif (
        pathlib.Path(temp).absolute().stat().st_size
        >= pathlib.Path(path_to_file).absolute().stat().st_size
    ):
        shutil.move(temp, path_to_file)
    else:
        pathlib.Path(temp).unlink(missing_ok=True)
        log_ = log_ or log
        log_.debug(f"{get_medialog(ele)} smaller then previous file")
    # set variables based on parent process


def addGlobalDir(input):
    if isinstance(input, pathlib.Path):
        dirSet.add(input.parent)
    else:
        dirSet.update(input)


def addLocalDir(path):
    localDirSet.add(path.resolve().parent)


def setDirectoriesDate():
    log.info("Setting Date for modified directories")
    output = set()
    rootDir = pathlib.Path(common_paths.get_save_location())
    log.debug(f"Original DirSet {list(dirSet)}")
    log.debug(f"rooDir {rootDir}")

    for ele in dirSet:
        output.add(ele)
        while not os.path.samefile(ele, rootDir) and not os.path.samefile(
            ele.parent, rootDir
        ):
            log.debug(f"Setting Dates ele:{ele} rootDir:{rootDir}")
            output.add(ele.parent)
            ele = ele.parent
    log.debug(f"Directories list {output}")
    for ele in output:
        set_time(ele, dates.get_current_time())


def get_item_total(item):
    return item["path"].absolute().stat().st_size


def alt_attempt_get(item):
    if item["type"] == "video":
        return attempt
    if item["type"] == "audio":
        return attempt2


def downloadspace():
    space_limit = config_data.get_system_freesize()
    if space_limit > 0 and space_limit > system.get_free():
        raise Exception(constants.getattr("SPACE_DOWNLOAD_MESSAGE"))


def log_download_progress(media_type):
    if media_type is None:
        return
    if (photo_count + audio_count + video_count + forced_skipped + skipped) % 20 == 0:
        log.debug(
            f"In progress -> {format_size(total_bytes )}) ({photo_count+audio_count+video_count} \
downloads total [{video_count} videos, {audio_count} audios, {photo_count} photos], \
            {forced_skipped} skipped, {skipped} failed)"
        )
