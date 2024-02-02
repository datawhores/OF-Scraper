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

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.style import Style
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.api.archive as archive
import ofscraper.api.labels as labels_api
import ofscraper.api.pinned as pinned
import ofscraper.classes.labels as labels
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

from ..api import timeline

sem = semaphoreDelayed(1)
log = logging.getLogger("shared")
import ofscraper.utils.args.read as read_args


def get_posts(model_id, username):
    args = read_args.retriveArgs()
    pinned_posts = []
    timeline_posts = []
    archived_posts = []
    labelled_posts = []
    options = args.like_area
    if "Pinned" in options or "All" in options:
        pinned_posts = pinned.get_pinned_post(model_id)
    if "Timeline" in options or "All" in options:
        timeline_posts = timeline.get_timeline_media(model_id, username, forced_after=0)
    if "Archived" in options or "All" in options:
        archived_posts = archive.get_archived_media(model_id, username, forced_after=0)
    if "Labels" in options or "All" in options:
        labels_ = labels_api.get_labels(model_id)
        labelled_posts_ = labels_api.get_labelled_posts(labels_, model_id)
        labelled_posts_ = list(
            map(lambda x: labels.Label(x, model_id, username), labelled_posts_)
        )
    log.debug(
        f"[bold]Number of Post Found[/bold] {len(pinned_posts) + len(timeline_posts) + len(archived_posts)}"
    )
    return pinned_posts + timeline_posts + archived_posts + labelled_posts


def get_posts_for_unlike(model_id, username):
    post = get_posts(model_id, username)
    return filter_for_favorited(post)


def get_post_for_like(model_id, username):
    post = get_posts(model_id, username)
    return filter_for_unfavorited(post)


def filter_for_unfavorited(posts: list) -> list:
    output = list(filter(lambda x: x.get("isFavorite") == False, posts))
    log.debug(f"[bold]Number of unliked post[/bold] {len(output)}")
    return output


def filter_for_favorited(posts: list) -> list:
    output = list(filter(lambda x: x.get("isFavorite") == True, posts))
    log.debug(f"[bold]Number of liked post[/bold] {len(output)}")
    return output


def get_post_ids(posts: list) -> list:
    valid_post = list(filter(lambda x: x.get("isOpened") == True, posts))
    return list(map(lambda x: x.get("id"), valid_post))


def like(model_id, username, ids: list):
    _like(model_id, username, ids, True)


def unlike(model_id, username, ids: list):
    _like(model_id, username, ids, False)


@run
async def _like(model_id, username, ids: list, like_action: bool):
    title = "Liking" if like_action else "Unliking"
    global sem
    sem.delay = 3
    with Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console.get_shared_console(),
    ) as overall_progress:
        async with sessionbuilder.sessionBuilder() as c:
            tasks = []
            task1 = overall_progress.add_task(f"{title} posts...\n", total=len(ids))

            [
                tasks.append(asyncio.create_task(_like_request(c, id, model_id)))
                for id in ids
            ]
            for count, coro in enumerate(asyncio.as_completed(tasks)):
                id = await coro
                log.debug(
                    f"ID: {id} Performed {'like' if like_action==True else 'unlike'} action"
                )

                if count + 1 % 60 == 0 and count + 1 % 50 == 0:
                    sem.delay = 15
                elif count + 1 % 60 == 0:
                    sem.delay = 3
                elif count + 1 % 50 == 0:
                    sem.delay = 30

                overall_progress.update(task1, advance=1, refresh=True)


async def _like_request(c, id, model_id):
    global sem
    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                async with c.requests(
                    constants.getattr("favoriteEP").format(id, model_id), "post"
                )() as r:
                    if r.ok:
                        return id
                    else:
                        log.debug(
                            f"[bold]timeline response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]timeline response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]timeline headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E
            finally:
                sem.release()
