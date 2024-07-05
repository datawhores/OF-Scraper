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

from humanfriendly import format_size

import ofscraper.download.utils.globals as common_globals
import ofscraper.models.selector as selector
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as config_data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
import ofscraper.utils.system.free as system
from ofscraper.download.utils.log import get_medialog
from ofscraper.download.utils.paths.media import add_path
from ofscraper.download.utils.send.message import set_send_msg


def add_additional_data(placeholderObj, ele):
    add_path(placeholderObj, ele)


def subProcessVariableInit(dateDict, userList, pipeCopy, pipeAltCopy, logCopy, argsCopy):
    common_globals.reset_globals()
    write_args.setArgs(argsCopy)
    dates.setLogDate(dateDict)
    selector.set_ALL_SUBS_DICT(userList)
    common_globals.process_split_globals(pipeCopy, pipeAltCopy,logCopy)
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
        raise Exception(s)
    elif (total - pathlib.Path(path).absolute().stat().st_size) < 0:
        s = f"{get_medialog(ele)} {path} size mixmatch target item too large: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        raise Exception(s)


async def check_forced_skip(ele, total):
    if total is None:
        return
    total = int(total)
    if total == 0:
        return 0
    file_size_max = settings.get_size_max(mediatype=ele.mediatype)
    file_size_min = settings.get_size_min(mediatype=ele.mediatype)
    if int(file_size_max) > 0 and (int(total) > int(file_size_max)):
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


def downloadspace(mediatype=None):
    space_limit = config_data.get_system_freesize(mediatype=mediatype)
    if space_limit > 0 and space_limit > system.get_free():
        raise Exception(constants.getattr("SPACE_DOWNLOAD_MESSAGE"))


async def get_hash(file_data, mediatype=None):
    return await asyncio.get_event_loop().run_in_executor(
        common_globals.thread, partial(hash.get_hash, file_data, mediatype=mediatype)
    )


async def get_data(ele):
    data = await asyncio.get_event_loop().run_in_executor(
        common_globals.thread,
        partial(cache.get, f"{ele.id}_{ele.username}_headers"),
    )
    return data


def get_unknown_content_type(ele):
    return (
        "mp4"
        if ele.mediatype.lower() == "videos"
        else "jpg" if ele.mediatype.lower() == "images" else None
    )


def is_bad_url(url):
    match = re.search(r"^https://([^/]+)", url)
    if not match:
        return False
    elif len(match.groups()) < 1:
        return False
    elif match.group(1) in constants.getattr("BAD_URL_HOST"):
        return True
