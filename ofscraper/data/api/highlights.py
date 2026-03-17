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
from ofscraper.data.api.common.logs.logs import trace_progress_log, trace_log_raw

log = logging.getLogger("shared")
API_S = "Stories"
API_H = "Highlights"

#############################################################################
#### Stories
##############################################################################


@run
async def get_stories_post(model_id, c=None):
    # Pass the raw generator
    generators = [scrape_stories(c, model_id)]
    return await process_stories_tasks(generators)


async def scrape_stories(c, user_id):
    url = of_env.getattr("highlightsWithAStoryEP").format(user_id)
    task = None
    try:
        task = progress_utils.api.add_job_task(
            f"[Stories] user id -> {user_id}", visible=True
        )
        async with c.requests_async(url=url) as r:
            if not (200 <= r.status < 300):
                log.debug(f"Stories API Error: {r.status} for {url}")
                return
            stories = await r.json_()
            stories = stories if isinstance(stories, list) else []
            if stories:
                yield stories
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
    finally:
        if task:
            progress_utils.api.remove_job_task(task)


async def process_stories_tasks(generators):
    responseArray = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Stories Pages Progress: {page_count}", visible=True
    )
    seen = set()
    queue = asyncio.Queue()

    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue
        page_count += 1
        progress_utils.api.update_overall_task(
            page_task, description=f"Stories Pages Progress: {page_count}"
        )
        if batch:
            new_posts = [
                p
                for p in batch
                if p.get("id") not in seen and not seen.add(p.get("id"))
            ]
            responseArray.extend(new_posts)
            trace_progress_log(f"{API_S} task", new_posts)
    trace_log_raw(f"{API_S} final", responseArray, final_count=True)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Stories')} {list(map(lambda x:x['id'],responseArray))}"
    )
    progress_utils.api.remove_overall_task(page_task)
    return responseArray


##############################################################################
#### Highlights
##############################################################################


@run
async def get_highlight_post(model_id, c=None):
    highlightLists = await get_highlight_list(model_id, c)
    return await get_highlights_via_list(highlightLists, c)


async def get_highlight_list(model_id, c=None):
    generators = [scrape_highlight_list(c, model_id)]
    return await process_task_get_highlight_list(generators)


async def get_highlights_via_list(highlightLists, c=None):
    generators = [scrape_highlights_from_list(c, i) for i in highlightLists]
    return await process_task_highlights(generators)


async def process_task_get_highlight_list(generators):
    highlightLists = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Highlights List Progress: {page_count}", visible=True
    )
    seen = set()
    queue = asyncio.Queue()

    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue
        page_count += 1
        progress_utils.api.update_overall_task(
            page_task, description=f"Highlights List Progress: {page_count}"
        )
        if batch:
            new_posts = [p for p in batch if p not in seen and not seen.add(p)]
            highlightLists.extend(new_posts)

    progress_utils.api.remove_overall_task(page_task)
    trace_log_raw(f"{API_H} list final", highlightLists, final_count=True)
    log.debug(
        common_logs.FINAL_COUNT_ITEM.format(
            "Highlight List", len(highlightLists), "highlights"
        )
    )
    return highlightLists


async def process_task_highlights(generators):
    highlightResponse = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Highlight Content Progress: {page_count}", visible=True
    )
    seen = set()
    queue = asyncio.Queue()

    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue
        page_count += 1
        progress_utils.api.update_overall_task(
            page_task, description=f"Highlight Content Progress: {page_count}"
        )
        if batch:
            new_posts = [
                p
                for p in batch
                if p.get("id") not in seen and not seen.add(p.get("id"))
            ]
            highlightResponse.extend(new_posts)
            trace_progress_log(f"{API_H} list posts task", new_posts)

    progress_utils.api.remove_overall_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Highlight List Posts')} {list(map(lambda x:x['id'],highlightResponse))}"
    )
    trace_log_raw(f"{API_H} lists posts final", highlightResponse, final_count=True)
    log.debug(
        common_logs.FINAL_COUNT_POST.format(
            "Highlight List Posts", {len(highlightResponse)}
        )
    )
    return highlightResponse


async def scrape_highlight_list(c, user_id, offset=0):
    current_offset = offset
    while True:
        url = of_env.getattr("highlightsWithStoriesEP").format(user_id, current_offset)
        task = None
        try:
            task = progress_utils.api.add_job_task(
                f"[Highlights] offset-> {current_offset}", visible=True
            )
            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Highlights List API Error: {r.status} for {url}")

                    break
                resp_data = await r.json_()
                data = get_highlightList(resp_data)
                if not data:
                    break
                yield data
                if not resp_data.get("hasMore"):
                    break
                current_offset += len(data)
        except Exception as E:
            log.traceback_(E)
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


async def scrape_highlights_from_list(c, id):
    url = of_env.getattr("storyEP").format(id)
    task = None
    try:
        task = progress_utils.api.add_job_task(f"[Highlights] ID -> {id}", visible=True)
        async with c.requests_async(url=url) as r:
            if not (200 <= r.status < 300):
                log.debug(f"Highlights API Error: {r.status} for {url}")
                return
            resp_data = await r.json_()
            stories = (
                resp_data.get("stories", []) if isinstance(resp_data, dict) else []
            )
            if stories:
                yield stories
    except Exception as E:
        log.traceback_(E)
    finally:
        if task:
            progress_utils.api.remove_job_task(task)


def get_highlightList(data):
    if not isinstance(data, dict):
        return []
    for ele in list(filter(lambda x: isinstance(x, list), data.values())):
        if len(list(filter(lambda x: isinstance(x.get("id"), (int, str)), ele))) > 0:
            return [x.get("id") for x in ele]
    return []


async def get_individual_highlights(id, c):
    """
    Compatibility wrapper for individual highlight fetching.
    """
    # This calls the internal worker we just modernized
    async for batch in scrape_highlights_from_list(c, id):
        return batch
    return []


async def get_individual_stories(id, c):
    """
    Bridge function: Consumes the new 'scrape_highlights_from_list' generator
    to return a standard list of stories for a specific ID.
    """
    data = []
    # We use 'async for' because scrape_highlights_from_list is now a generator
    async for batch in scrape_highlights_from_list(c, id):
        if batch:
            data.extend(batch)
    return data
