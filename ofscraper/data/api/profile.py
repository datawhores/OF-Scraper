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

import ofscraper.managers.manager as manager
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings

from ...utils import encoding

console = Console()
log = logging.getLogger("shared")
API = "Profile"


# can get profile from username or id
def scrape_profile(username: Union[int, str]) -> dict:
    with manager.Manager.session.get_ofsession() as c:
        return scrape_profile_helper(c, username)


def scrape_profile_helper(c, username: Union[int, str]):
    data = cache.get(f"username_{username}", default=None)
    log.trace(f"username date: {data}")
    if data and not settings.get_settings().update_profile:
        return data
    try:
        with c.requests(of_env.getattr("profileEP").format(username)) as r:
            if r.status == 404:
                return {"username": of_env.getattr("DELETED_MODEL_PLACEHOLDER")}

            cache.set(
                f"username_{username}",
                r.json(),
                int(of_env.getattr("PROFILE_DATA_EXPIRY")),
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
    url = of_env.getattr("profileEP").format(username)
    if data and not settings.get_settings().update_profile:
        return data
    try:

        log.info(f"getting {username} with {url}")
        async with c.requests_async(url) as r:
            if r.status == 404:
                return {"username": of_env.getattr("DELETED_MODEL_PLACEHOLDER")}
            cache.set(
                f"username_{username}",
                await r.json_(),
                int(of_env.getattr("PROFILE_DATA_EXPIRY_ASYNC")),
            )

            log.trace(f"username date: {await r.json_()}")
            return await r.json_()
    except Exception as E:

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


def parse_profile(profile: dict) -> tuple:
    # Identify valid media URLs from the raw profile dict
    media_urls = list(
        filter(
            None, [profile.get("avatar"), profile.get("header"), profile.get("profile")]
        )
    )

    output = []
    for ele in media_urls:
        # Standardizing structure and casing for hardening
        output.append(
            {
                "id": xxh128(ele).hexdigest(),
                "postedAt": profile.get("joinDate"),
                "text": profile.get("about"),
                "responsetype": "Profile",  # Capitalized
                "mediatype": "Photo",  # Capitalized
                "value": "Free",  # Hardened value for price filtering
                "media": [
                    {
                        "id": xxh128(ele[:-1]).hexdigest(),
                        "type": "photo",
                        "canView": True,
                        "source": {"source": ele},
                        "createdAt": profile.get("joinDate"),
                    }
                ],
            }
        )

    # Keep info tuple consistent for existing profile info prints
    info = (
        encoding.encode_utf_16(profile["name"]),
        profile["username"],
        profile["id"],
        profile["joinDate"],
        profile["postsCount"],
        profile["photosCount"],
        profile["videosCount"],
        profile["audiosCount"],
        profile["archivedPostsCount"],
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
    c = c or manager.Manager.session.get_ofsession()
    with c as c:
        return get_id_helper(c, username)


def get_id_helper(c, username):
    if username.isnumeric():
        return username
    if username == of_env.getattr("DELETED_MODEL_PLACEHOLDER"):
        raise Exception("could not get ID")
    id = cache.get(f"model_id_{username}")
    if id:
        return id
    try:

        log.info(f"to get id {username}")

        with c.requests(of_env.getattr("profileEP").format(username)) as r:
            id = r.json()["id"]
            cache.set(f"model_id_{username}", id, of_env.getattr("DAY_SECONDS"))

            return id

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
