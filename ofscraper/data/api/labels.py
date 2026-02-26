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
from ofscraper.data.api.common.check import update_check
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")
API = "labels"


@run
async def get_labels(model_id, c=None):
    labels_ = await get_labels_data(model_id, c=c)
    labels_ = (
        labels_
        if not settings.get_settings().label
        else list(
            filter(
                lambda x: x.get("name").lower() in settings.get_settings().label,
                labels_,
            )
        )
    )
    data = await get_posts_for_labels(labels_, model_id, c=c)
    update_check(data, model_id, None, API)

    return data


async def get_labels_data(model_id, c=None):
    generators = [scrape_labels(c, model_id)] 
    return await process_tasks_labels(generators)


async def get_posts_for_labels(labels, model_id, c=None):
    # This list will now hold raw generator objects
    generators = []
    for label in labels:
        generators.append(scrape_posts_labels(c, label, model_id))

    labels_final = await process_tasks_get_posts_for_labels(generators, labels)
    return labels_final


async def process_tasks_labels(generators):
    output = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Labels Progress: {page_count}", visible=True
    )
    
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
            page_task,
            description=f"Labels Progress: {page_count}",
        )
        
        if batch:
            output.extend(batch)

    progress_utils.api.remove_overall_task(page_task)
    return output


async def process_tasks_get_posts_for_labels(generators, labels):
    """
    Fixed Orchestrator: Uses a Queue to aggregate posts from label generators
    simultaneously without create_task(generator) errors.
    """
    responseDict = get_default_label_dict(labels)
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Labels Content Progress: {page_count}", visible=True
    )
    queue = asyncio.Queue()

    # The Producer: Feeds the tuple (label_info, batch) into the queue
    async def producer(gen):
        try:
            async for label_info, batch in gen:
                await queue.put((label_info, batch))
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    # Start all producers concurrently as real Tasks
    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        result = await queue.get()
        
        if result is None:
            active_workers -= 1
            continue

        label_info, batch = result
        page_count += 1
        progress_utils.api.update_overall_task(
            page_task, description=f"Labels Content Progress: {page_count}"
        )

        if batch:
            # Deduplicate within the context of this specific label
            new_posts = label_dedupe(responseDict[label_info["id"]]["seen"], batch)
            trace_progress_log(f"{API} content tasks", new_posts)
            responseDict[label_info["id"]]["posts"].extend(new_posts)

    # Clean up 'seen' sets before returning
    [label.pop("seen", None) for label in responseDict.values()]
    
    trace_log_raw(f"{API} content final", list(responseDict.values()), final_count=True)
    progress_utils.api.remove_overall_task(page_task)
    
    return list(responseDict.values())


async def scrape_labels(c, model_id, offset=0):
    current_offset = offset
    while True:
        url = of_env.getattr("labelsEP").format(model_id, current_offset)
        task = None
        try:
            task = progress_utils.api.add_job_task(
                f"labels offset -> {current_offset}", visible=True
            )
            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    break

                data = await r.json_()
                media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
                batch = media_lists[0] if media_lists else []

                if not batch:
                    break
                
                yield batch

                if not data.get("hasMore"):
                    break
                
                current_offset += len(batch)
        except Exception as E:
            log.traceback_(E)
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


async def scrape_posts_labels(c, label, model_id, offset=0):
    current_offset = offset
    while True:
        url = of_env.getattr("labelledPostsEP").format(model_id, current_offset, label["id"])
        task = None
        try:
            task = progress_utils.api.add_job_task(
                f": getting posts from label -> {label['name']}", visible=True
            )
            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    break

                data = await r.json_()
                media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
                batch = media_lists[0] if media_lists else []

                if not batch:
                    break

                # Yield label and batch together for the consumer to sort
                yield label, batch

                if not data.get("hasMore"):
                    break
                
                current_offset += len(batch)
        except Exception as E:
            log.traceback_(E)
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


def label_dedupe(seen, labelArray):
    return [
        post
        for post in labelArray
        if post.get("id") not in seen and not seen.add(post.get("id"))
    ]


def get_default_label_dict(labels):
    output = {}
    for label in labels:
        label_copy = label.copy()
        output[label_copy["id"]] = label_copy
        output[label_copy["id"]]["seen"] = set()
        output[label_copy["id"]]["posts"] = []
    return output