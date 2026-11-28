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

from ofscraper.commands.scraper.actions.download import stop
import logging
import traceback

import ofscraper.data.api.common.incomplete as incomplete
import ofscraper.data.api.common.logs.strings as common_logs

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.tasks import collect_pages
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_progress_log, trace_log_raw

log = logging.getLogger("shared")
API_S = "Stories"
API_H = "Highlights"

#############################################################################
#### Stories
##############################################################################


@run
@stop.fetching
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
                incomplete.mark_incomplete(user_id, API_S, f"HTTP {r.status}")
                return
            stories = await r.json_()
            stories = stories if isinstance(stories, list) else []
            if stories:
                yield stories
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        incomplete.mark_incomplete(user_id, API_S, f"{type(E).__name__}: {E}")
    finally:
        if task:
            progress_utils.api.remove_job_task(task)


async def process_stories_tasks(generators):
    responseArray = await collect_pages(
        generators,
        "Stories Pages Progress",
        lambda new_posts: trace_progress_log(f"{API_S} task", new_posts),
    )
    trace_log_raw(f"{API_S} final", responseArray, final_count=True)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Stories')} {list(map(lambda x:x['id'],responseArray))}"
    )
    return responseArray


##############################################################################
#### Highlights
##############################################################################


@run
@stop.fetching
async def get_highlight_post(model_id, c=None):
    highlightLists = await get_highlight_list(model_id, c)
    return await get_highlights_via_list(highlightLists, c)


@stop.fetching
async def get_highlight_list(model_id, c=None):
    generators = [scrape_highlight_list(c, model_id)]
    return await process_task_get_highlight_list(generators)


@stop.fetching
async def get_highlights_via_list(highlightLists, c=None):
    generators = [scrape_highlights_from_list(c, i) for i in highlightLists]
    return await process_task_highlights(generators)


async def process_task_get_highlight_list(generators):
    # pages of highlight ids
    highlightLists = await collect_pages(
        generators, "Highlights List Progress", key=lambda highlight_id: highlight_id
    )
    trace_log_raw(f"{API_H} list final", highlightLists, final_count=True)
    log.debug(
        common_logs.FINAL_COUNT_ITEM.format(
            "Highlight List", len(highlightLists), "highlights"
        )
    )
    return highlightLists


async def process_task_highlights(generators):
    highlightResponse = await collect_pages(
        generators,
        "Highlight Content Progress",
        lambda new_posts: trace_progress_log(f"{API_H} list posts task", new_posts),
    )
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
                    incomplete.mark_incomplete(user_id, API_H, f"HTTP {r.status}")
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
            incomplete.mark_incomplete(user_id, API_H, f"{type(E).__name__}: {E}")
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
                incomplete.mark_incomplete(None, API_H, f"highlight {id}: HTTP {r.status}")
                return
            resp_data = await r.json_()
            stories = (
                resp_data.get("stories", []) if isinstance(resp_data, dict) else []
            )
            # a story doesn't name its highlight: keep the one it was asked
            # for under, for the stories table (#728)
            stories = [
                dict(story, highlightId=id) for story in stories if isinstance(story, dict)
            ]
            if stories:
                yield stories
    except Exception as E:
        log.traceback_(E)
        incomplete.mark_incomplete(None, API_H, f"highlight {id}: {type(E).__name__}: {E}")
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


@stop.fetching
async def get_individual_highlights(id, c):
    """
    Compatibility wrapper for individual highlight fetching.
    """
    # This calls the internal worker we just modernized
    async for batch in scrape_highlights_from_list(c, id):
        return batch
    return []


@stop.fetching
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
