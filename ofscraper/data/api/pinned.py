r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )   ( || (____/\| ) \ \__
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
from ofscraper.data.api.common.timeline import process_posts_as_individual
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
        data = process_posts_as_individual()
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

    page_task = progress_utils.api.add_overall_task(
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
                progress_utils.api.update_overall_task(
                    page_task,
                    description=f"Pinned Content Pages Progress: {page_count}",
                )

                if result:
                    new_posts = [
                        post
                        for post in result
                        if post.get("id") not in seen and not seen.add(post.get("id"))
                    ]
                    log.debug(
                        f"{common_logs.PROGRESS_IDS.format('Pinned')} {list(map(lambda x:x.get('id'),new_posts))}"
                    )
                    trace_progress_log(f"{API} tasks", new_posts)
                    responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    progress_utils.api.remove_overall_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Pinned')} {list(map(lambda x:x.get('id'),responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(common_logs.FINAL_COUNT_POST.format("Pinned", len(responseArray)))
    return responseArray


async def scrape_pinned_posts(c, model_id, timestamp=None, count=0) -> list:
    posts = []
    new_tasks = []
    task = None

    if timestamp and (
        float(timestamp) > (settings.get_settings().before).float_timestamp
    ):
        return [], []

    url = of_env.getattr("timelinePinnedEP").format(model_id, count)

    try:
        task_label = f"[Pinned] Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(of_env.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"
        task = progress_utils.api.add_job_task(task_label, visible=True)

        log.debug(f"trying to access pinned posts with url:{url}")

        async with c.requests_async(url=url) as r:
            if not (200 <= r.status < 300):
                log.error(f"Pinned API Error: {r.status}")
                return [], []

            log.debug(f"successfully accessed pinned posts with url:{url}")

            data = await r.json_()
            if not isinstance(data, dict):
                return [], []

            posts = data.get("list", [])
            posts = list(
                sorted(posts, key=lambda x: float(x.get("postedAtPrecise", 0)))
            )
            posts = list(
                filter(
                    lambda x: float(x.get("postedAtPrecise", 0))
                    > float(timestamp or 0),
                    posts,
                )
            )

            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(of_env.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"

            if not posts:
                log.debug(f"{log_id} -> number of pinned post found 0")
                return [], []

            log.debug(f"{log_id} -> number of pinned post found {len(posts)}")
            trace_progress_log(f"{API} requests", posts)

            # Recursive task logic
            new_ts = posts[-1].get("postedAtPrecise")

            if str(new_ts) == str(timestamp):
                return posts, []

            new_tasks.append(
                asyncio.create_task(
                    scrape_pinned_posts(
                        c,
                        model_id,
                        timestamp=new_ts,
                        count=count + len(posts),
                    )
                )
            )

    except Exception as E:
        log.error("Pinned branch failed")
        log.traceback_(E)
        log.traceback_(traceback.format_exc())

        return [], []  # Keep it moving
    finally:
        if task:
            progress_utils.api.remove_job_task(task)

    return posts, new_tasks
