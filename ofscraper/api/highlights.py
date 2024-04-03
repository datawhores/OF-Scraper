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
import contextvars
import logging
import traceback

from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
sem = None
attempt = contextvars.ContextVar("attempt")


#############################################################################
#### Stories
####
##############################################################################
@run
async def get_stories_post_progress(model_id, c=None):
    global sem
    sem = semaphoreDelayed(1)
    tasks = []
    job_progress = progress_utils.stories_progress

    tasks.append(
        asyncio.create_task(scrape_stories(c, model_id, job_progress=job_progress))
    )

    data = await process_stories_tasks(tasks)

    progress_utils.stories_layout.visible = False
    return data


@run
async def get_stories_post(model_id, c=None):
    global sem
    sem = semaphoreDelayed(1)
    tasks = []
    with progress_utils.set_up_api_stories():
        tasks.append(
            asyncio.create_task(
                scrape_stories(
                    c, model_id, job_progress=progress_utils.stories_progress
                )
            )
        )
        return await process_stories_tasks(tasks)


async def scrape_stories(c, user_id, job_progress=None) -> list:
    global sem
    global tasks
    stories = None
    attempt.set(0)

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
            new_tasks = []
            await sem.acquire()
            await asyncio.sleep(1)
            try:
                attempt.set(attempt.get(0) + 1)
                task = (
                    job_progress.add_task(
                        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} : user id -> {user_id}",
                        visible=True,
                    )
                    if job_progress
                    else None
                )
                async with c.requests(
                    url=constants.getattr("highlightsWithAStoryEP").format(user_id)
                )() as r:
                    if r.ok:
                        stories = await r.json_()
                        log.debug(
                            f"stories: -> found stories ids {list(map(lambda x:x.get('id'),stories))}"
                        )
                        log.trace(
                            "stories: -> stories raw {posts}".format(
                                posts="\n\n".join(
                                    list(
                                        map(
                                            lambda x: f"scrapeinfo stories: {str(x)}",
                                            stories,
                                        )
                                    )
                                )
                            )
                        )
                    else:
                        log.debug(
                            f"[bold]stories response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]stories response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]stories headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                await asyncio.sleep(1)
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                (
                    job_progress.remove_task(task)
                    if job_progress and task != None
                    else None
                )

            return stories, new_tasks


async def process_stories_tasks(tasks):
    responseArray = []
    page_count = 0
    overall_progress = progress_utils.overall_progress
    page_task = overall_progress.add_task(
        f"Stories Pages Progress: {page_count}", visible=True
    )

    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * max(len(tasks), 2)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        result, new_tasks_batch = await task
                        new_tasks.extend(new_tasks_batch)
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task,
                            description=f"Stories Content Pages Progress: {page_count}",
                        )
                        responseArray.extend(result)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
        except TimeoutError as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        tasks = new_tasks

    overall_progress.remove_task(page_task)

    log.trace(
        "stories raw duped {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"dupedinfo stories: {str(x)}", responseArray))
            )
        )
    )
    log.debug(f"[bold]stories Count with Dupes[/bold] {len(responseArray)} found")
    seen = set()
    new_posts = [
        post
        for post in responseArray
        if post["id"] not in seen and not seen.add(post["id"])
    ]

    log.trace(f"stories postids {list(map(lambda x:x.get('id'),new_posts))}")
    log.trace(
        "post raw unduped {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"undupedinfo stories: {str(x)}", new_posts))
            )
        )
    )
    log.debug(f"[bold]Stories Count without Dupes[/bold] {len(new_posts)} found")

    return new_posts


##############################################################################
#### Highlights
####
##############################################################################


@run
async def get_highlight_post_progress(model_id, c=None):
    highlightLists = await get_highlight_list_progress(model_id, c)
    return await get_highlights_via_list_progress(highlightLists, c)


async def get_highlight_list_progress(model_id, c=None):
    global sem
    sem = semaphoreDelayed(1)

    tasks = []
    tasks.append(
        asyncio.create_task(
            scrape_highlight_list(
                c, model_id, job_progress=progress_utils.highlights_progress
            )
        )
    )
    return await process_task_get_highlight_list(tasks)


async def get_highlights_via_list_progress(highlightLists, c=None):
    tasks = []
    [
        tasks.append(
            asyncio.create_task(
                scrape_highlights(c, i, job_progress=progress_utils.highlights_progress)
            )
        )
        for i in highlightLists
    ]
    return await process_task_highlights(tasks)


@run
async def get_highlight_post(model_id, c=None):
    highlightList = await get_highlight_list(model_id, c)
    return await get_highlights_via_list(highlightList, c)


async def get_highlight_list(model_id, c=None):
    global sem
    sem = semaphoreDelayed(1)

    with progress_utils.set_up_api_highlights_lists():
        tasks = []
        tasks.append(
            asyncio.create_task(
                scrape_highlight_list(
                    c, model_id, job_progress=progress_utils.highlights_progress
                )
            )
        )
        return await process_task_get_highlight_list(tasks)


async def get_highlights_via_list(highlightLists, c):
    tasks = []
    with progress_utils.set_up_api_highlights():

        [
            tasks.append(
                asyncio.create_task(
                    scrape_highlights(
                        c, i, job_progress=progress_utils.highlights_progress
                    )
                )
            )
            for i in highlightLists
        ]
        return await process_task_highlights(tasks)


async def process_task_get_highlight_list(tasks):
    highlightLists = []

    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
        f"Highlights List Pages Progress: {page_count}", visible=True
    )
    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * max(len(tasks), 2)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        result, new_tasks_batch = await task
                        new_tasks.extend(new_tasks_batch)
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task,
                            description=f"Highlights List Pages Progress: {page_count}",
                        )
                        highlightLists.extend(result)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
        except TimeoutError as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())

        tasks = new_tasks
    overall_progress.remove_task(page_task)
    return highlightLists


async def process_task_highlights(tasks):
    highlightResponse = []
    page_count = 0
    overall_progress = progress_utils.overall_progress
    page_task = overall_progress.add_task(
        f"Highlight Content via List Pages Progress: {page_count}", visible=True
    )
    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * max(len(tasks), 2)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        result, new_tasks_batch = await task
                        new_tasks.extend(new_tasks_batch)
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task,
                            description=f"Highlight Content via List Pages Progress: {page_count}",
                        )
                        highlightResponse.extend(result)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
        except TimeoutError as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        tasks = new_tasks
    log.trace(
        "highlight raw duped {posts}".format(
            posts="\n\n".join(
                list(
                    map(lambda x: f"dupedinfo heighlight: {str(x)}", highlightResponse)
                )
            )
        )
    )
    log.debug(f"[bold]highlight Count with Dupes[/bold] {len(highlightResponse)} found")
    seen = set()
    new_posts = [
        post
        for post in highlightResponse
        if post["id"] not in seen and not seen.add(post["id"])
    ]

    log.trace(f"highlights postids {list(map(lambda x:x.get('id'),new_posts))}")
    log.trace(
        "highlights raw unduped {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"undupedinfo highlights: {str(x)}", new_posts))
            )
        )
    )
    log.debug(f"[bold]Highlights Count without Dupes[/bold] {len(new_posts)} found")

    return new_posts


async def scrape_highlight_list(c, user_id, job_progress=None, offset=0) -> list:
    global sem
    attempt.set(0)
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
            new_tasks = []
            await sem.acquire()
            await asyncio.sleep(1)
            try:
                attempt.set(attempt.get(0) + 1)
                task = (
                    job_progress.add_task(
                        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} scraping highlight list  offset-> {offset}",
                        visible=True,
                    )
                    if job_progress
                    else None
                )
                async with c.requests(
                    url=constants.getattr("highlightsWithStoriesEP").format(
                        user_id, offset
                    )
                )() as r:
                    if r.ok:
                        resp_data = await r.json_()
                        log.trace(
                            f"highlights list: -> found highlights list data {resp_data}"
                        )
                        data = get_highlightList(resp_data)
                        log.debug(f"highlights list: -> found list ids {data}")

                    else:
                        log.debug(
                            f"[bold]highlight list response status code:[/bold]{r.status}"
                        )
                        log.debug(
                            f"[bold]highlight list response:[/bold] {await r.text_()}"
                        )
                        log.debug(f"[bold]highlight list headers:[/bold] {r.headers}")
            except Exception as E:
                await asyncio.sleep(1)
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                (
                    job_progress.remove_task(task)
                    if job_progress and task != None
                    else None
                )

            return data, new_tasks


async def scrape_highlights(c, id, job_progress=None) -> list:
    global sem
    attempt.set(0)
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
            new_tasks = []
            await sem.acquire()
            await asyncio.sleep(1)
            try:
                attempt.set(attempt.get(0) + 1)
                task = (
                    job_progress.add_task(
                        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} highlights id -> {id}",
                        visible=True,
                    )
                    if job_progress
                    else None
                )
                async with c.requests(
                    url=constants.getattr("storyEP").format(id)
                )() as r:
                    if r.ok:
                        resp_data = await r.json_()
                        log.trace(f"highlights: -> found highlights data {resp_data}")
                        log.debug(
                            f"highlights: -> found ids {list(map(lambda x:x.get('id'),resp_data['stories']))}"
                        )
                    else:
                        log.debug(f"[bold]highlight status code:[/bold]{r.status}")
                        log.debug(f"[bold]highlight response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]h ighlight headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                await asyncio.sleep(1)
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                (
                    job_progress.remove_task(task)
                    if job_progress and task != None
                    else None
                )

            return resp_data["stories"], new_tasks


def get_highlightList(data):
    for ele in list(filter(lambda x: isinstance(x, list), data.values())):
        if (
            len(
                list(
                    filter(
                        lambda x: isinstance(x.get("id"), int)
                        and data.get("hasMore") != None,
                        ele,
                    )
                )
            )
            > 0
        ):
            return list(map(lambda x: x.get("id"), ele))
    return []


def get_individual_highlights(id):
    return get_individual_stories(id)
    # with c.requests(constants.getattr("highlightSPECIFIC").format(id))() as r:
    #     if r.ok:
    #         log.trace(f"highlight raw highlight individua; {r.json()}")
    #         return r.json()
    #     else:
    #         log.debug(f"[bold]highlight response status code:[/bold]{r.status}")
    #         log.debug(f"[bold]highlightresponse:[/bold] {await r.text_()}")
    #         log.debug(f"[bold]highlight headers:[/bold] {r.headers}")


def get_individual_stories(id, c=None):
    with sessionbuilder.sessionBuilder(backend="httpx") as c:
        with c.requests(constants.getattr("storiesSPECIFIC").format(id))() as r:
            if r.ok:
                log.trace(f"highlight raw highlight individua; {r.json_()}")
                return r.json()
            else:
                log.debug(f"[bold]highlight response status code:[/bold]{r.status}")
                log.debug(f"[bold]highlightresponse:[/bold] {r.text_()}")
                log.debug(f"[bold]highlight headers:[/bold] {r.headers}")
