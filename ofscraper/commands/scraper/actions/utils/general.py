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

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.hash as hash
import ofscraper.utils.of_env.of_env as of_env

# get_hash's default thread: the current DownloadContext's pool
_CURRENT_POOL = object()


async def get_hash(file_data, thread=_CURRENT_POOL):
    """thread is the pool to hash on (None: the loop's default)."""
    return await asyncio.get_event_loop().run_in_executor(
        common_globals.thread if thread is _CURRENT_POOL else thread,
        partial(
            hash.get_hash,
            file_data,
        ),
    )


# Content types whose subtype isn't the file's usual extension
_EXTENSIONS = {
    "video/quicktime": "mov",
    "video/x-ms-wmv": "wmv",
    "video/x-ms-asf": "asf",
    "video/x-msvideo": "avi",
    "video/x-matroska": "mkv",
    "audio/x-matroska": "mka",
    "video/x-flv": "flv",
    "video/mp2t": "ts",
    "video/3gpp": "3gp",
    "video/3gpp2": "3g2",
    "video/x-m4v": "m4v",
    "audio/x-m4a": "m4a",
    "audio/x-wav": "wav",
}
# Content types that say nothing about the file's format
_GENERIC = {"application/octet-stream", "binary/octet-stream"}


def extension_for(content_type, fallback=None):
    """The file extension for a reply's Content-Type header.

    Usually the subtype ("video/mp4" -> "mp4"), but a few subtypes aren't
    extensions players know ("video/quicktime" is a ".mov"). A missing or
    generic type gives the fallback.
    """
    mime = (content_type or "").split(";")[0].strip().lower()
    subtype = mime.split("/")[-1]
    if not subtype or mime in _GENERIC:
        return fallback
    return _EXTENSIONS.get(mime, subtype)


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
    for ele in of_env.getattr("BAD_URL_HOST"):
        if re.search(ele, match.group(1)):
            return True
    return False
