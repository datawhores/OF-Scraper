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
import ofscraper.api.timeline as timeline
import ofscraper.classes.labels as labels
import ofscraper.classes.posts as posts_
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.system.system as system
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

sem = semaphoreDelayed(1)
log = logging.getLogger("shared")


@run
async def get_posts(model_id, username):
    responses = []
    final_post_areas = set(areas.get_like_area())
    tasks = []
    with progress_utils.setup_api_split_progress_live():
        async with sessionbuilder.sessionBuilder() as c:
            while True:
                max_count = min(
                    constants.getattr("API_MAX_AREAS"),
                    system.getcpu_count(),
                    len(final_post_areas),
                )
                if not bool(tasks) and not bool(final_post_areas):
                    break
                for _ in range(max_count - len(tasks)):
                    if "Pinned" in final_post_areas:
                        tasks.append(
                            asyncio.create_task(
                                pinned.get_pinned_posts_progress(model_id, c)
                            )
                        )
                        progress_utils.pinned_layout.visible = True
                        final_post_areas.remove("Pinned")
                    elif "Timeline" in final_post_areas:
                        tasks.append(
                            asyncio.create_task(
                                timeline.get_timeline_posts_progress(
                                    model_id=model_id,
                                    username=username,
                                    c=c,
                                    forced_after=read_args.retriveArgs().after or 0,
                                )
                            )
                        )
                        progress_utils.timeline_layout.visible = True
                        final_post_areas.remove("Timeline")
                    if "Archived" in final_post_areas:
                        tasks.append(
                            asyncio.create_task(
                                archive.get_archived_posts_progress(
                                    model_id=model_id,
                                    username=username,
                                    c=c,
                                    forced_after=read_args.retriveArgs().after or 0,
                                )
                            )
                        )
                        progress_utils.archived_layout.visible = True
                        final_post_areas.remove("Archived")

                    elif "Labels" in final_post_areas:
                        tasks.append(
                            asyncio.create_task(
                                labels_api.get_labels_posts_progress(
                                    model_id=model_id, c=c
                                )
                            )
                        )
                        progress_utils.labelled_layout.visible = True
                        final_post_areas.remove("Labels")
                if not bool(tasks):
                    break
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                await asyncio.sleep(1)
                tasks = list(pending)
                for results in done:
                    try:
                        data = await results or []
                        responses.extend(data)
                        await asyncio.sleep(1)
                    except Exception as E:
                        await asyncio.sleep(1)
                        log.debug(E)
                        continue
    return pre_filter(
        list(
            map(
                lambda x: posts_.Post(x, model_id=model_id, username=username),
                responses,
            )
        )
    )


def get_posts_for_unlike(model_id, username):
    post = get_posts(model_id, username)
    return filter_for_favorited(post)


def get_post_for_like(model_id, username):
    post = get_posts(model_id, username)
    return filter_for_unfavorited(post)


def filter_for_unfavorited(posts: list) -> list:
    output = list(filter(lambda x: x.favorited == False, posts))
    log.debug(f"[bold]Number of unliked post[/bold] {len(output)}")
    return output


def filter_for_favorited(posts: list) -> list:
    output = list(filter(lambda x: x.favorited == True, posts))
    log.debug(f"[bold]Number of liked post[/bold] {len(output)}")
    return output


def pre_filter(posts):
    valid_post = list(filter(lambda x: x.opened, posts))
    seen = set()
    return [
        post for post in valid_post if post.id not in seen and not seen.add(post.id)
    ]


def get_post_ids(posts: list) -> list:
    return list(map(lambda x: x.id, posts))


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
