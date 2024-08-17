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
import re
from functools import partial


import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.hash as hash
from ofscraper.actions.utils.paths.media import add_path


def add_additional_data(placeholderObj, ele):
    add_path(placeholderObj, ele)


async def set_profile_cache_helper(ele):
    if ele.postid and ele.responsetype == "profile":
        await asyncio.get_event_loop().run_in_executor(
            common_globals.thread, partial(cache.set, ele.postid, True)
        )


async def get_hash(file_data, mediatype=None):
    return await asyncio.get_event_loop().run_in_executor(
        common_globals.thread, partial(hash.get_hash, file_data, mediatype=mediatype)
    )


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
    for ele in constants.getattr("BAD_URL_HOST"):
        if re.search(ele, match.group(1)):
            return True
    return False
