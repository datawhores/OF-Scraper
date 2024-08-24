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

import logging
import traceback
from typing import Union

from rich.console import Console
from xxhash import xxh128

import  ofscraper.runner.manager as manager2
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants

from ...utils import encoding

console = Console()
log = logging.getLogger("shared")
API = "profile"


# can get profile from username or id
def scrape_profile(username: Union[int, str]) -> dict:
    with manager2.Manager.get_ofsession(
        backend="httpx",
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
        async with c.requests_async(url) as r:
            if r.status == 404:
                return {"username": constants.getattr("DELETED_MODEL_PLACEHOLDER")}
            cache.set(
                f"username_{username}",
                await r.json_(),
                int(constants.getattr("PROFILE_DATA_EXPIRY_ASYNC")),
            )

            log.trace(f"username date: {await r.json_()}")
            return await r.json_()
    except Exception as E:

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
    c = c or manager2.Manager.get_ofsession(
        backend="httpx",
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

            return id

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
