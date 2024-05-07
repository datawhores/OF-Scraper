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
import logging
import traceback
from typing import Union

from rich.console import Console
from xxhash import xxh128

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants

from ..utils import encoding

console = Console()
log = logging.getLogger("shared")


# can get profile from username or id
def scrape_profile(username: Union[int, str]) -> dict:
    with sessionManager.sessionManager(
        backend="httpx",
        limit=constants.getattr("API_MAX_CONNECTION"),
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        return scrape_profile_helper(c, username)


def scrape_profile_helper(c, username: Union[int, str]):
    data = cache.get(f"username_{username}", default=None)
    log.trace(f"username date: {data}")
    if data and not read_args.retriveArgs().update_profile:
        return data
    try:
        with c.requests(constants.getattr("profileEP").format(username)) as r:
            if r.status == 404:
                return {"username": constants.getattr("DELETED_MODEL_PLACEHOLDER")}

            cache.set(
                f"username_{username}",
                r.json(),
                int(constants.getattr("PROFILE_DATA_EXPIRY")),
            )
            cache.close()
            log.trace(f"username date: {r.json()}")
            return r.json()
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def scrape_profile_helper_async(c, username: Union[int, str]):
    data = cache.get(f"username_{username}", default=None)
    log.trace(f"username date: {data}")
    url = constants.getattr("profileEP").format(username)
    if data and not read_args.retriveArgs().update_profile:
        return data
    try:

        log.info(f"getting {username} with {url}")
        await asyncio.sleep(1)
        async with c.requests_async(url) as r:
            if r.status == 404:
                return {"username": constants.getattr("DELETED_MODEL_PLACEHOLDER")}
            cache.set(
                f"username_{username}",
                await r.json_(),
                int(constants.getattr("PROFILE_DATA_EXPIRY_ASYNC")),
            )
            cache.close()
            log.trace(f"username date: {await r.json_()}")
            return await r.json_()
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


def parse_profile(profile: dict) -> tuple:
    media = []
    media.append(profile.get("avatar"))
    media.append(profile.get("header"))
    media.append(profile.get("profile"))
    media = list(filter(lambda x: x is not None, media))

    output = []
    for ele in media:
        output.append(
            {
                "url": ele,
                "responsetype": "profile",
                "mediatype": "photo",
                "value": "free",
                "createdAt": profile["joinDate"],
                "text": profile["about"],
                "id": xxh128(ele).hexdigest(),
                "mediaid": xxh128(ele[:-1]).hexdigest(),
            }
        )

    name = encoding.encode_utf_16(profile["name"])
    username = profile["username"]
    id_ = profile["id"]
    join_date = profile["joinDate"]
    posts_count = profile["postsCount"]
    photos_count = profile["photosCount"]
    videos_count = profile["videosCount"]
    audios_count = profile["audiosCount"]
    archived_posts_count = profile["archivedPostsCount"]
    info = (
        name,
        username,
        id_,
        join_date,
        posts_count,
        photos_count,
        videos_count,
        audios_count,
        archived_posts_count,
    )

    return output, info


def print_profile_info(info):
    header_fmt = "Name: {} | Username: {} | ID: {} | Joined: {}\n"
    info_fmt = (
        "- {} posts\n -- {} photos\n -- {} videos\n -- {} audios\n- {} archived posts"
    )
    final_fmt = header_fmt + info_fmt
    log.info(final_fmt.format(*info))


def get_id(username, c=None):
    c = c or sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    )
    with c as c:
        return get_id_helper(c, username)


def get_id_helper(c, username):
    if username.isnumeric():
        return username
    if username == constants.getattr("DELETED_MODEL_PLACEHOLDER"):
        raise Exception("could not get ID")
    id = cache.get(f"model_id_{username}")
    if id:
        return id
    try:

        log.info(f"to get id {username}")

        with c.requests(constants.getattr("profileEP").format(username)) as r:
            id = r.json()["id"]
            cache.set(f"model_id_{username}", id, constants.getattr("DAY_SECONDS"))
            cache.close()
            return id

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
