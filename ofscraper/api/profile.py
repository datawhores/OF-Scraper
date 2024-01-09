r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import contextvars
import logging
from typing import Union

from rich.console import Console
from tenacity import (
    Retrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)
from xxhash import xxh128

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants

from ..utils import encoding

console = Console()
log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


# can get profile from username or id
def scrape_profile(username: Union[int, str]) -> dict:
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return scrape_profile_helper(c, username)


def scrape_profile_helper(c, username: Union[int, str]):
    id = cache.get(f"username_{username}", None)
    log.trace(f"username date: {id}")
    if id:
        return id
    log.info(
        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} to get profile {username}"
    )

    for _ in Retrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            with c.requests(constants.getattr("profileEP").format(username))() as r:
                if r.ok:
                    cache.set(
                        f"username_{username}",
                        r.json(),
                        int(constants.getattr("HOURLY_EXPIRY") * 2),
                    )
                    cache.close()
                    log.trace(f"username date: {r.json()}")
                    return r.json()
                elif r.status == 404:
                    attempt.set(0)
                    return {"username": "modeldeleted"}
                else:
                    log.debug(f"[bold]profile response status code:[/bold]{r.status}")
                    log.debug(f"[bold]profile response:[/bold] {r.text_()}")
                    log.debug(f"[bold]profile headers:[/bold] {r.headers}")
                    r.raise_for_status()


def parse_profile(profile: dict) -> tuple:
    media = []
    media.append(profile.get("avatar"))
    media.append(profile.get("header"))
    media.append(profile.get("profile"))
    media = list(filter(lambda x: x != None, media))

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


def get_id(username):
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        return get_id_helper(c, username)


def get_id_helper(c, username):
    id = cache.get(f"model_id_{username}")
    if id:
        return id
    for _ in Retrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        attempt.set(attempt.get(0) + 1)
        with _:
            with c.requests(constants.getattr("profileEP").format(username))() as r:
                if r.ok:
                    id = r.json()["id"]
                    cache.set(
                        f"model_id_{username}", id, constants.getattr("DAY_SECONDS")
                    )
                    cache.close()
                    return id
                else:
                    log.debug(f"[bold]id response status code:[/bold]{r.status}")
                    log.debug(f"[bold]id response:[/bold] {r.text_()}")
                    log.debug(f"[bold]id headers:[/bold] {r.headers}")
                    r.raise_for_status()
