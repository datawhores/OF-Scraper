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

import ofscraper.api.common.logs as common_logs
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


#############################################################################
#### Stories
####
##############################################################################
@run
async def get_stories_post_progress(model_id, c=None):
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
    stories = None
    new_tasks = []
    task = None

    await asyncio.sleep(1)
    url = constants.getattr("highlightsWithAStoryEP").format(user_id)
    try:
        task = (
            job_progress.add_task(
                f"user id -> {user_id}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url=url) as r:
            stories = await r.json_()
            log.debug(
                f"stories: -> found stories ids {list(map(lambda x:x.get('id'),stories))}"
            )
            log.trace(
                "stories: -> stories raw {posts}".format(
                    posts="\n\n".join(
                        map(
                            lambda x: f"scrapeinfo stories: {str(x)}",
                            stories,
                        )
                    )
                )
            )
    except asyncio.TimeoutError as _:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        (job_progress.remove_task(task) if job_progress and task is not None else None)

    return stories, new_tasks


async def process_stories_tasks(tasks):
    responseArray = []
    page_count = 0
    overall_progress = progress_utils.overall_progress
    page_task = overall_progress.add_task(
        f"Stories Pages Progress: {page_count}", visible=True
    )

    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                overall_progress.update(
                    page_task,
                    description=f"Stories Content Pages Progress: {page_count}",
                )
                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Stories')} {list(map(lambda x:x['id'],new_posts))}"
                )
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Stories')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                new_posts,
                            )
                        )
                    )
                )

                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue

        tasks = new_tasks
    overall_progress.remove_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Stories')} {list(map(lambda x:x['id'],responseArray))}"
    )
    log.trace(
        f"{common_logs.FINAL_RAW.format('Stories')}".format(
            posts="\n\n".join(
                map(lambda x: f"{common_logs.RAW_INNER} {x}", responseArray)
            )
        )
    )
    log.debug(f"{common_logs.FINAL_COUNT.format('Stories')} {len(responseArray)}")

    return responseArray


##############################################################################
#### Highlights
####
##############################################################################


@run
async def get_highlight_post_progress(model_id, c=None):
    highlightLists = await get_highlight_list_progress(model_id, c)
    return await get_highlights_via_list_progress(highlightLists, c)


async def get_highlight_list_progress(model_id, c=None):
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
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                overall_progress.update(
                    page_task,
                    description=f"Highlights List Pages Progress: {page_count}",
                )
                new_posts = [
                    post for post in result if post not in seen and not seen.add(post)
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Highlight List')} {list(map(lambda x:x,new_posts))}"
                )

                highlightLists.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    overall_progress.remove_task(page_task)
    log.trace(
        f"{common_logs.FINAL_IDS.format('Highlight List')} {map(lambda x:x,highlightLists)}"
    )
    log.debug(
        f"{common_logs.FINAL_COUNT.format('Highlight List')} {len(highlightLists)}"
    )

    return highlightLists


async def process_task_highlights(tasks):
    highlightResponse = []
    page_count = 0
    overall_progress = progress_utils.overall_progress
    page_task = overall_progress.add_task(
        f"Highlight Content via List Pages Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                overall_progress.update(
                    page_task,
                    description=f"Highlights Content via list Pages Progress: {page_count}",
                )
                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Highlight List Posts')} {list(map(lambda x:x['id'],new_posts))}"
                )
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Highlight List Posts')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                new_posts,
                            )
                        )
                    )
                )

                highlightResponse.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
        log.debug(
            f"{common_logs.FINAL_IDS.format('Highlight List Posts')} {list(map(lambda x:x['id'],highlightResponse))}"
        )
        log.trace(
            f"{common_logs.FINAL_RAW.format('Highlight List Posts')}".format(
                posts="\n\n".join(
                    map(lambda x: f"{common_logs.RAW_INNER} {x}", highlightResponse)
                )
            )
        )
        log.debug(
            f"{common_logs.FINAL_COUNT.format('Highlight List Posts')} {len(highlightResponse)}"
        )
    return highlightResponse


async def scrape_highlight_list(c, user_id, job_progress=None, offset=0) -> list:
    new_tasks = []
    await asyncio.sleep(1)
    url = constants.getattr("highlightsWithStoriesEP").format(user_id, offset)
    task = None

    try:
        task = (
            job_progress.add_task(
                f"scraping highlight list  offset-> {offset}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url) as r:
            resp_data = await r.json_()
            log.trace(f"highlights list: -> found highlights list data {resp_data}")
            data = get_highlightList(resp_data)
            log.debug(f"highlights list: -> found list ids {data}")

    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        (job_progress.remove_task(task) if job_progress and task is not None else None)

    return data, new_tasks


async def scrape_highlights(c, id, job_progress=None) -> list:
    new_tasks = []
    await asyncio.sleep(1)
    url = constants.getattr("storyEP").format(id)
    task = None

    try:
        task = (
            job_progress.add_task(
                f"highlights id -> {id}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url=url) as r:
            resp_data = await r.json_()
            log.trace(f"highlights: -> found highlights data {resp_data}")
            log.debug(
                f"highlights: -> found ids {list(map(lambda x:x.get('id'),resp_data['stories']))}"
            )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        (job_progress.remove_task(task) if job_progress and task is not None else None)

    return resp_data["stories"], new_tasks


def get_highlightList(data):
    for ele in list(filter(lambda x: isinstance(x, list), data.values())):
        if (
            len(
                list(
                    filter(
                        lambda x: isinstance(x.get("id"), int)
                        and data.get("hasMore") is not None,
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


def get_individual_stories(id, c=None):
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        with c.requests_async(constants.getattr("storiesSPECIFIC").format(id)) as r:
            log.trace(f"highlight raw highlight individua; {r.json_()}")
            return r.json()
