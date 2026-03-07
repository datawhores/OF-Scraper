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
import ofscraper.managers.manager as manager
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.common.check import update_check
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log

paid_content_list_name = "list"
log = logging.getLogger("shared")
API = "Purchased"


@run
async def get_paid_posts(username, model_id, c=None):
    tasks = []
    # Create the coroutine; it will return an AsyncGenerator when awaited
    tasks.append(scrape_paid(c, username))
    data = await process_tasks(tasks)
    update_check(data, model_id, None, API)
    return data


async def process_tasks(generators):
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Paid Content Pages Progress: {page_count}", visible=True
    )
    responseArray = []
    seen = set()
    queue = asyncio.Queue()

    # The Producer: Feeds the queue from the generator
    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    # Start the producers as proper tasks
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
            description=f"Paid Content Pages Progress: {page_count}",
        )
        if batch:
            new_posts = [
                post
                for post in batch
                if post.get("id") not in seen and not seen.add(post.get("id"))
            ]
            log.debug(
                f"{common_logs.PROGRESS_IDS.format('Paid')} {list(map(lambda x:x['id'],new_posts))}"
            )
            trace_progress_log(f"{API} tasks", new_posts)
            responseArray.extend(new_posts)

    progress_utils.api.remove_overall_task(page_task)
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(common_logs.FINAL_COUNT_POST.format("Paid", len(responseArray)))
    return responseArray


async def scrape_paid(c, username, offset=0):
    """
    Async Generator version of scrape_paid.
    Yields batches of posts immediately to save memory and prevent data loss on crash.
    """
    current_offset = offset

    while True:
        url = of_env.getattr("purchased_contentEP").format(current_offset, username)
        task = None
        try:
            task = progress_utils.api.add_job_task(
                f"scrape paid offset -> {current_offset} username -> {username}",
                visible=True,
            )

            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Paid API Error at offset {current_offset}: {r.status}")
                    break

                data = await r.json_()
                if not isinstance(data, dict):
                    log.debug(
                        f"API returned unexpected format at offset {current_offset}"
                    )
                    break

                trace_progress_log(f"{API} individual requests", data)

                media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
                batch = media_lists[0] if media_lists else []

                if not batch:
                    break

                # YIELD BATCH IMMEDIATELY
                yield batch

                # EXIT LOGIC
                if not data.get("hasMore"):
                    break

                # SAFETY: Prevent stuck offset loop
                new_offset = current_offset + len(batch)
                if new_offset <= current_offset:
                    break

                current_offset = new_offset

        except Exception as E:
            log.info(f"Failed scrape paid offset {current_offset}")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


@run
async def get_all_paid_posts():
    async with manager.Manager.session.aget_ofsession(
        sem_count=of_env.getattr("SCRAPE_PAID_SEMS"),
    ) as c:
        tasks = await create_tasks_scrape_paid(c)
        data = await process_tasks_all_paid(tasks)
        return create_all_paid_dict(data)


async def create_tasks_scrape_paid(c):
    """
    Creates parallel workers for scraping all paid content.
    Returns a list of coroutines (not tasks yet) to be scheduled.
    """
    min_posts = 80
    tasks = []
    allpaid = cache.get("purchased_all", default=[])

    if len(allpaid) > min_posts:
        splitArrays = [i for i in range(0, len(allpaid), min_posts)]
        for i in range(0, len(splitArrays) - 1):
            tasks.append(scrape_all_paid(c, required=min_posts, offset=splitArrays[i]))
        tasks.append(scrape_all_paid(c, offset=splitArrays[-1], required=None))
    else:
        tasks.append(scrape_all_paid(c))
    return tasks


async def process_tasks_all_paid(generators):
    output = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"[Scrape Paid] Pages Progress: {page_count}", visible=True
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
            page_task, description=f"[Scrape Paid] Pages Progress: {page_count}"
        )
        if batch:
            output.extend(batch)
            trace_progress_log(f"{API} all users tasks", batch)

    progress_utils.api.remove_overall_task(page_task)
    trace_log_raw(f"{API} all users final", output, final_count=True)
    cache.set(
        "purchased_all",
        list(map(lambda x: x.get("id"), output)),
        expire=of_env.getattr("RESPONSE_EXPIRY"),
    )
    return output


async def scrape_all_paid(c, offset=0, required=None):
    """
    Async Generator Worker Loop for global paid content.
    """
    current_offset = offset
    items_retrieved = 0

    while True:
        url = of_env.getattr("purchased_contentALL").format(current_offset)
        task = None
        try:
            task = progress_utils.api.add_job_task(
                f"scrape entire paid page offset={current_offset}", visible=True
            )
            async with c.requests_async(url) as r:
                if not (200 <= r.status < 300):
                    log.debug(
                        f"Global Paid API Error at offset {current_offset}: {r.status}"
                    )
                    break

                data = await r.json_()
                if not isinstance(data, dict):
                    break

                trace_progress_log(f"{API} all users requests", data)

                media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
                batch = media_lists[0] if media_lists else []

                if not batch:
                    break

                # YIELD BATCH IMMEDIATELY
                yield batch

                items_retrieved += len(batch)

                # EXIT LOGIC
                if not data.get("hasMore"):
                    break

                if required is not None and items_retrieved >= required:
                    break

                # SAFETY: Move pointer forward
                new_offset = current_offset + len(batch)
                if new_offset <= current_offset:
                    break
                current_offset = new_offset

        except Exception as E:
            log.info(f"Scrape all paid failed at offset {current_offset}")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


def create_all_paid_dict(paid_content):
    user_dict = {}
    for ele in paid_content:
        user_id = ele.get("fromUser", {}).get("id") or ele.get("author", {}).get("id")
        user_dict.setdefault(str(user_id), []).append(ele)
    [update_check(val, key, None, API) for key, val in user_dict.items()]
    return user_dict


def get_individual_paid_post(username, model_id, postid):
    data = get_paid_posts(username, model_id)
    postid = int(postid)
    posts = list(filter(lambda x: int(x.get("id")) == postid, data))
    return posts[0] if posts else None
