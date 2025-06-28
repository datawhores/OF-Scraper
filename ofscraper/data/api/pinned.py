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
import math
import traceback

import arrow

import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.common.check import update_check
from ofscraper.data.api.common.timeline import process_individual
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
import ofscraper.utils.settings as settings


log = logging.getLogger("shared")
API = "pinned"


@run
async def get_pinned_posts(model_id, c=None, post_id=None):
    post_id = post_id or []
    if len(post_id) == 0 or len(post_id) > of_env.getattr(
        "MAX_PINNED_INDIVIDUAL_SEARCH"
    ):
        tasks = get_tasks(c, model_id)
        data = await process_tasks(tasks)
    elif len(post_id) <= of_env.getattr("MAX_PINNED_INDIVIDUAL_SEARCH"):
        data = process_individual()
    update_check(data, model_id, None, API)
    return data


def get_tasks(c, model_id):
    tasks = []
    tasks.append(
        asyncio.create_task(
            scrape_pinned_posts(
                c,
                model_id,
                timestamp=(
                    settings.get_settings().after.float_timestamp
                    if settings.get_settings().after
                    else None
                ),
            )
        )
    )
    return tasks


async def process_tasks(tasks):
    responseArray = []
    page_count = 0

    page_task = progress_utils.add_api_task(
        f"Pinned Content Pages Progress: {page_count}", visible=True
    )
    seen = set()

    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                progress_utils.update_api_task(
                    page_task,
                    description=f"Pinned Content Pages Progress: {page_count}",
                )
                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Pinned')} {list(map(lambda x:x['id'],new_posts))}"
                )
                trace_progress_log(f"{API} tasks", new_posts)
                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    progress_utils.remove_api_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Pinned')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(f"{common_logs.FINAL_COUNT.format('Pinned')} {len(responseArray)}")
    return responseArray


async def scrape_pinned_posts(c, model_id, timestamp=None, count=0) -> list:
    posts = None

    if timestamp and (
        float(timestamp) > (settings.get_settings().before).float_timestamp
    ):
        return [], []
    url = of_env.getattr("timelinePinnedEP").format(model_id, count)
    log.debug(url)

    new_tasks = []
    posts = []
    try:

        task = progress_utils.add_api_job_task(
            f"[Pinned] Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(of_env.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}",
            visible=True,
        )
        log.debug(
            f"trying to access  {API.lower()} posts with url:{url} timestamp:{timestamp if timestamp is not None else 'initial'}"
        )
        async with c.requests_async(url=url) as r:
            log.debug(
                f"successfully accessed {API.lower()} posts with url:{url} timestamp:{timestamp if timestamp is not None else 'initial'}"
            )
            posts = (await r.json_())["list"]
            posts = list(sorted(posts, key=lambda x: float(x["postedAtPrecise"])))
            posts = list(
                filter(
                    lambda x: float(x["postedAtPrecise"]) > float(timestamp or 0),
                    posts,
                )
            )
            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(of_env.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"
            if not posts:
                posts = []
            if len(posts) == 0:
                log.debug(f"{log_id} -> number of pinned post found 0")
            else:
                log.debug(f"{log_id} -> number of pinned post found {len(posts)}")
                log.debug(
                    f"{log_id} -> first date {posts[0].get('createdAt') or posts[0].get('postedAt')}"
                )
                log.debug(
                    f"{log_id} -> last date {posts[-1].get('createdAt') or posts[-1].get('postedAt')}"
                )
                log.debug(
                    f"{log_id} -> found pinned post IDs {list(map(lambda x:x.get('id'),posts))}"
                )
                trace_progress_log(f"{API} requests", posts)
                new_tasks.append(
                    asyncio.create_task(
                        scrape_pinned_posts(
                            c,
                            model_id,
                            timestamp=posts[-1]["postedAtPrecise"],
                            count=count + len(posts),
                        )
                    )
                )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        progress_utils.remove_api_job_task(task)

    return posts, new_tasks
