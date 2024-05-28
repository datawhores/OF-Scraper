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
from functools import partial

import psutil
from humanfriendly import format_size

import ofscraper.download.shared.globals as common_globals
import ofscraper.models.selector as selector
import ofscraper.utils.args.write as write_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
import ofscraper.utils.system.free as system
from ofscraper.download.shared.utils.log import get_medialog
from ofscraper.download.shared.utils.media import add_path
from ofscraper.download.shared.utils.message import send_msg, set_send_msg
from ofscraper.download.shared.utils.progress import update_total


def add_additional_data(placeholderObj, ele):
    add_path(placeholderObj, ele)


def subProcessVariableInit(dateDict, userList, pipeCopy, logCopy, argsCopy):
    common_globals.reset_globals()
    write_args.setArgs(argsCopy)
    dates.setLogDate(dateDict)
    selector.set_ALL_SUBS_DICT(userList)
    common_globals.process_split_globals(pipeCopy, logCopy)
    set_send_msg()


async def size_checker(path, ele, total, name=None):
    name = name or ele.filename
    if total == 0:
        return True
    if not pathlib.Path(path).exists():
        s = f"{get_medialog(ele)} {path} was not created"
        raise Exception(s)
    elif total - pathlib.Path(path).absolute().stat().st_size > 500:
        s = f"{get_medialog(ele)} {name} size mixmatch target: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        await asyncio.get_event_loop().run_in_executor(
            common_globals.thread, partial(cache.set, f"{ele.id}_headers", None)
        )
        raise Exception(s)
    elif (total - pathlib.Path(path).absolute().stat().st_size) < 0:
        s = f"{get_medialog(ele)} {path} size mixmatch target item too large: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        await asyncio.get_event_loop().run_in_executor(
            common_globals.thread, partial(cache.set, f"{ele.id}_headers", None)
        )
        raise Exception(s)


async def check_forced_skip(ele, total):
    if total == None:
        return
    total = int(total)
    if total == 0:
        return 0
    file_size_limit = settings.get_size_limit(mediatype=ele.mediatype)
    file_size_min = settings.get_size_min(mediatype=ele.mediatype)
    if int(file_size_limit) > 0 and (int(total) > int(file_size_limit)):
        ele.mediatype = "forced_skipped"
        common_globals.log.debug(
            f"{get_medialog(ele)} {format_size(total)} over size limit"
        )
        return 0
    elif int(file_size_min) > 0 and (int(total) < int(file_size_min)):
        ele.mediatype = "forced_skipped"
        common_globals.log.debug(
            f"{get_medialog(ele)} {format_size(total)} under size min"
        )
        return 0


async def set_profile_cache_helper(ele):
    if ele.postid and ele.responsetype == "profile":
        await asyncio.get_event_loop().run_in_executor(
            common_globals.thread, partial(cache.set, ele.postid, True)
        )


def get_item_total(item):
    return item["path"].absolute().stat().st_size


def alt_attempt_get(item):
    if item["type"] == "video":
        return common_globals.attempt
    if item["type"] == "audio":
        return common_globals.attempt2


def downloadspace(mediatype=None):
    space_limit = config_data.get_system_freesize(mediatype=mediatype)
    if space_limit > 0 and space_limit > system.get_free():
        raise Exception(constants.getattr("SPACE_DOWNLOAD_MESSAGE"))


async def get_hash(file_data, mediatype=None):
    return await asyncio.get_event_loop().run_in_executor(
        common_globals.thread, partial(hash.get_hash, file_data, mediatype=mediatype)
    )


def get_resume_size(tempholderObj, mediatype=None):
    if not settings.get_auto_resume(mediatype=mediatype):
        pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
        return 0
    return (
        0
        if not pathlib.Path(tempholderObj.tempfilepath).exists()
        else pathlib.Path(tempholderObj.tempfilepath).absolute().stat().st_size
    )


async def get_data(ele):
    data = await asyncio.get_event_loop().run_in_executor(
        common_globals.thread,
        partial(cache.get, f"{ele.id}_headers"),
    )
    return data


def get_unknown_content_type(ele):
    return (
        "mp4"
        if ele.mediatype.lower() == "videos"
        else "jpg" if ele.mediatype.lower() == "images" else None
    )


async def batch_total_change_helper(past_total, new_total):
    if not new_total and not past_total:
        return
    elif not past_total:
        await send_msg((None, 0, new_total))
    elif past_total and new_total - past_total != 0:
        await send_msg((None, 0, new_total - past_total))


async def total_change_helper(past_total, new_total):
    if not new_total and not past_total:
        return
    elif not past_total:
        await update_total(new_total)
    elif past_total and new_total - past_total != 0:
        await update_total(new_total - past_total)


def is_bad_url(url):
    match = re.search(r"^https://([^/]+)", url)
    if not match:
        return False
    elif len(match.groups()) < 1:
        return False
    elif match.group(1) in constants.getattr("BAD_URL_HOST"):
        return True


def get_ideal_chunk_size(total_size, curr_file):
    """
    Suggests a chunk size based on file size and a calculated available memory buffer.

    Args:
        file_size (int): Size of the file being downloaded in bytes.

    Returns:
        int: Suggested chunk size in bytes.
    """
    curr_file_size = (
        pathlib.Path(curr_file).absolute().stat().st_size
        if pathlib.Path(curr_file).exists()
        else 0
    )
    file_size = total_size - curr_file_size

    # Estimate available memory (considering a buffer for system operations)
    available_memory = (
        psutil.virtual_memory().available - 1024 * 1024 * 512
    )  # Reserve 512MB buffer

    # Target a chunk size that utilizes a reasonable portion of available memory
    max_chunk_size = min(
        available_memory // 512, constants.getattr("MAX_CHUNK_SIZE")
    )  # Max 10MB
    # Adjust chunk size based on file size (consider smaller sizes for larger files, with minimum)
    ideal_chunk_size = min(max_chunk_size, file_size // 512)
    ideal_chunk_size = max(
        ideal_chunk_size - (ideal_chunk_size % 4096),
        constants.getattr("MIN_CHUNK_SIZE"),
    )  # Minimum 4KB chunk
    return ideal_chunk_size


def get_update_count(total_size, curr_file, chunk_size):
    curr_file_size = (
        pathlib.Path(curr_file).absolute().stat().st_size
        if pathlib.Path(curr_file).exists()
        else 0
    )
    file_size = total_size - curr_file_size

    return max((file_size // chunk_size) // constants.getattr("CHUNK_UPDATE_COUNT"), 1)


def send_bar_message()