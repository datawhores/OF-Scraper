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

import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log

log = logging.getLogger("shared")
API_S = "stories"
API_H = "highlights"

#############################################################################
#### Stories
##############################################################################

@run
async def get_stories_post(model_id, c=None):
    tasks = []
    tasks.append(asyncio.create_task(scrape_stories(c, model_id)))
    return await process_stories_tasks(tasks)


async def scrape_stories(c, user_id) -> list:
    stories = []
    new_tasks = []
    task = None

    url = of_env.getattr("highlightsWithAStoryEP").format(user_id)
    try:
        task = progress_utils.api.add_job_task(
            f"[Stories] user id -> {user_id}",
            visible=True,
        )
        log.debug(f"trying to access {API_S.lower()} with url:{url}  user_id:{user_id}")

        async with c.requests_async(url=url) as r:
            # FIX: Success range check
            if not (200 <= r.status < 300):
                log.error(f"Stories API Error: {r.status} for {user_id}")
                return [], []

            stories = await r.json_()
            # Safety check for unexpected return types
            stories = stories if isinstance(stories, list) else []

            log.debug(f"successfully accessed {API_S.lower()} with url:{url}")
            trace_progress_log(f"{API_S} requests", stories)

    except Exception as E:
        log.error(f"Failed to scrape stories for {user_id}: {E}")
        log.traceback_(E)
        return [], [] # Fail gracefully to prevent UI stall

    finally:
        if task:
            progress_utils.api.remove_job_task(task)

    return stories, new_tasks


async def process_stories_tasks(tasks):
    responseArray = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
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
                progress_utils.api.update_overall_task(
                    page_task,
                    description=f"Stories Content Pages Progress: {page_count}",
                )
                
                # Check that result is iterable
                if result:
                    new_posts = [
                        post
                        for post in result
                        if post.get("id") not in seen and not seen.add(post.get("id"))
                    ]
                    responseArray.extend(new_posts)

            except Exception as E:
                log.traceback_(E)
                continue

        tasks = new_tasks
        
    progress_utils.api.remove_overall_task(page_task)
    log.debug(common_logs.FINAL_COUNT_POST.format('Stories', len(responseArray)))
    return responseArray


##############################################################################
#### Highlights
##############################################################################

@run
async def get_highlight_post(model_id, c=None):
    highlightLists = await get_highlight_list(model_id, c)
    return await get_highlights_via_list(highlightLists, c)


async def get_highlight_list(model_id, c=None):
    tasks = []
    tasks.append(asyncio.create_task(scrape_highlight_list(c, model_id)))
    return await process_task_get_highlight_list(tasks)


async def get_highlights_via_list(highlightLists, c=None):
    tasks = []
    for i in highlightLists:
        tasks.append(asyncio.create_task(scrape_highlights_from_list(c, i)))
    return await process_task_highlights(tasks)


async def process_task_get_highlight_list(tasks):
    highlightLists = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
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
                progress_utils.api.update_overall_task(
                    page_task,
                    description=f"Highlights List Pages Progress: {page_count}",
                )
                if result:
                    new_posts = [
                        post for post in result if post not in seen and not seen.add(post)
                    ]
                    highlightLists.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                continue
        tasks = new_tasks

    progress_utils.api.remove_overall_task(page_task)
    return highlightLists


async def process_task_highlights(tasks):
    highlightResponse = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Highlight Content Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                progress_utils.api.update_overall_task(
                    page_task,
                    description=f"Highlights content progress: {page_count}",
                )
                if result:
                    new_posts = [
                        post
                        for post in result
                        if post.get("id") not in seen and not seen.add(post.get("id"))
                    ]
                    highlightResponse.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                continue
        tasks = new_tasks

    progress_utils.api.remove_overall_task(page_task)
    return highlightResponse


async def scrape_highlight_list(c, user_id, offset=0) -> list:
    new_tasks = []
    url = of_env.getattr("highlightsWithStoriesEP").format(user_id, offset)
    task = None
    data = []

    try:
        task = progress_utils.api.add_job_task(
            f"[Highlights] scraping list offset-> {offset}",
            visible=True,
        )
        async with c.requests_async(url) as r:
            if not (200 <= r.status < 300):
                return [], []

            resp_data = await r.json_()
            data = get_highlightList(resp_data)
            
    except Exception as E:
        log.error(f"Highlight list failed: {E}")
        return [], []
    finally:
        if task:
            progress_utils.api.remove_job_task(task)

    return data, new_tasks


async def scrape_highlights_from_list(c, id) -> list:
    new_tasks = []
    url = of_env.getattr("storyEP").format(id)
    task = None

    try:
        task = progress_utils.api.add_job_task(
            f"[Highlights] ID -> {id}",
            visible=True,
        )
        async with c.requests_async(url=url) as r:
            if not (200 <= r.status < 300):
                return [], []

            resp_data = await r.json_()
            # FIX: Safe extraction of stories
            stories = resp_data.get("stories", []) if isinstance(resp_data, dict) else []
            return stories, new_tasks
            
    except Exception as E:
        log.debug(f"Highlight extraction failed for ID {id}: {E}")
        return [], []
    finally:
        if task:
            progress_utils.api.remove_job_task(task)


def get_highlightList(data):
    if not isinstance(data, dict):
        return []
    for ele in list(filter(lambda x: isinstance(x, list), data.values())):
        if (
            len(
                list(
                    filter(
                        lambda x: isinstance(x.get("id"), (int, str)),
                        ele,
                    )
                )
            )
            > 0
        ):
            return list(map(lambda x: x.get("id"), ele))
    return []


async def get_individual_stories(id, c):
    url = of_env.getattr("storiesSPECIFIC").format(id)
    async with c.requests_async(url) as r:
        if not (200 <= r.status < 300):
            return []
        data = await r.json_()
        return data if isinstance(data, list) else [data]