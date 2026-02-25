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
    # Top level entry point
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
    tasks = []
    tasks.append(asyncio.create_task(scrape_labels(c, model_id)))
    return await process_tasks_labels(tasks)


async def get_posts_for_labels(labels, model_id, c=None):
    tasks = []
    for label in labels:
        tasks.append(asyncio.create_task(scrape_posts_labels(c, label, model_id)))
    
    labels_final = await process_tasks_get_posts_for_labels(tasks, labels)
    return labels_final


async def process_tasks_labels(tasks):
    responseArray = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Label Names Pages Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count += 1
                progress_utils.api.update_overall_task(
                    page_task,
                    description=f"Label Names Pages Progress: {page_count}",
                )

                if result:
                    new_posts = [
                        post
                        for post in result
                        if post.get("id") not in seen and not seen.add(post.get("id"))
                    ]
                    responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    progress_utils.api.remove_overall_task(page_task)
    return responseArray


async def scrape_labels(c, model_id, offset=0):
    labels = []
    new_tasks = []
    url = of_env.getattr("labelsEP").format(model_id, offset)
    task = None
    
    try:
        task = progress_utils.api.add_job_task(f"labels offset -> {offset}", visible=True)
        async with c.requests_async(url) as r:
            if not (200 <= r.status < 300):
                log.error(f"Labels API Error: {r.status}")
                return [], []

            data = await r.json_()
            if not isinstance(data, dict): return [], []

            media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
            labels = media_lists[0] if media_lists else []

            if data.get("hasMore") and len(labels) > 0:
                new_offset = offset + len(labels)
                # Infinite loop guard
                if new_offset != offset:
                    new_tasks.append(asyncio.create_task(scrape_labels(c, model_id, offset=new_offset)))
            
            return labels, new_tasks
            
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        return [], []
    finally:
        if task:
            progress_utils.api.remove_job_task(task)


async def process_tasks_get_posts_for_labels(tasks, labels):
    responseDict = get_default_label_dict(labels)
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Labels Progress: {page_count}", visible=True
    )

    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                label, posts, batch_new_tasks = await task
                page_count += 1
                progress_utils.api.update_overall_task(page_task, description=f"Labels Progress: {page_count}")
                
                if posts:
                    new_posts = label_dedupe(responseDict[label["id"]]["seen"], posts)
                    responseDict[label["id"]]["posts"].extend(new_posts)
                
                new_tasks.extend(batch_new_tasks)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    [label.pop("seen", None) for label in responseDict.values()]
    progress_utils.api.remove_overall_task(page_task)
    return list(responseDict.values())


async def scrape_posts_labels(c, label, model_id, offset=0):
    posts = []
    new_tasks = []
    url = of_env.getattr("labelledPostsEP").format(model_id, offset, label["id"])
    task = None

    try:
        task = progress_utils.api.add_job_task(f": getting posts from label -> {label['name']}", visible=True)
        async with c.requests_async(url) as r:
            if not (200 <= r.status < 300):
                log.error(f"Label Content API Error: {r.status} for label {label['id']}")
                return label, [], []

            data = await r.json_()
            if not isinstance(data, dict): return label, [], []

            media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
            posts = media_lists[0] if media_lists else []

            if data.get("hasMore") and len(posts) > 0:
                new_offset = offset + len(posts)
                if new_offset != offset:
                    new_tasks.append(asyncio.create_task(scrape_posts_labels(c, label, model_id, offset=new_offset)))

            return label, posts, new_tasks

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        return label, [], []
    finally:
        if task:
            progress_utils.api.remove_job_task(task)


def label_dedupe(seen, labelArray):
    return [post for post in labelArray if post.get("id") not in seen and not seen.add(post.get("id"))]


def get_default_label_dict(labels):
    output = {}
    for label in labels:
        label_copy = label.copy()
        output[label_copy["id"]] = label_copy
        output[label_copy["id"]]["seen"] = set()
        output[label_copy["id"]]["posts"] = []
    return output