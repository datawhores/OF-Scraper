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
import ofscraper.utils.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.data.api.common.check import update_check
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_progress_log

paid_content_list_name = "list"
log = logging.getLogger("shared")
API = "Purchased"


@run
async def get_paid_posts(username, model_id, c=None):
    tasks = []
    tasks.append(asyncio.create_task(scrape_paid(c, username)))
    data = await process_tasks(tasks)
    update_check(data, model_id, None, API)
    return data


async def process_tasks(tasks):
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"Paid Content Pages Progress: {page_count}", visible=True
    )
    responseArray = []
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
                    description=f"Paid Content Pages Progress: {page_count}",
                )
                if result:
                    new_posts = [
                        post
                        for post in result
                        if post.get("id") not in seen and not seen.add(post.get("id"))
                    ]
                    log.debug(
                        f"{common_logs.PROGRESS_IDS.format('Paid')} {list(map(lambda x:x.get('id'),new_posts))}"
                    )
                    trace_progress_log(f"{API} tasks", new_posts)
                    responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    progress_utils.api.remove_overall_task(page_task)
    log.debug(common_logs.FINAL_COUNT_POST.format("Paid", len(responseArray)))
    return responseArray


async def scrape_paid(c, username, offset=0):
    media = []
    new_tasks = []
    task = None
    url = of_env.getattr("purchased_contentEP").format(offset, username)

    try:
        task = progress_utils.api.add_job_task(
            f"scrape paid offset -> {offset} username -> {username}",
            visible=True,
        )

        async with c.requests_async(url) as r:
            if not (200 <= r.status < 300):
                log.error(f"Paid API Error: {r.status}")
                return [], []

            data = await r.json_()
            if not isinstance(data, dict):
                return [], []

            trace_progress_log(f"{API} all users requests", data)

            # Safely extract list from data values
            media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
            media = media_lists[0] if media_lists else []

            if data.get("hasMore") and len(media) > 0:
                new_offset = offset + len(media)
                if new_offset == offset:
                    return media, []

                new_tasks.append(
                    asyncio.create_task(scrape_paid(c, username, offset=new_offset))
                )
            return media, new_tasks

    except Exception as E:
        log.error(f"Failed scrape paid offset {offset}")
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        return [], []
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
    min_posts = 80
    tasks = []
    allpaid = cache.get("purchased_all", default=[])

    if len(allpaid) > min_posts:
        splitArrays = [i for i in range(0, len(allpaid), min_posts)]
        for i in range(0, len(splitArrays) - 1):
            tasks.append(
                asyncio.create_task(
                    scrape_all_paid(c, required=min_posts, offset=splitArrays[i])
                )
            )
        tasks.append(
            asyncio.create_task(
                scrape_all_paid(c, offset=splitArrays[-1], required=None)
            )
        )
    else:
        tasks.append(asyncio.create_task(scrape_all_paid(c)))
    return tasks


async def process_tasks_all_paid(tasks):
    output = []
    page_count = 0
    page_task = progress_utils.api.add_overall_task(
        f"[Scrape Paid] Pages Progress: {page_count}", visible=True
    )

    while tasks:
        new_tasks_batch = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks = await task
                new_tasks_batch.extend(new_tasks)
                page_count += 1
                progress_utils.api.update_overall_task(
                    page_task, description=f"[Scrape Paid] Pages Progress: {page_count}"
                )
                if result:
                    output.extend(result)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
        tasks = new_tasks_batch

    progress_utils.api.remove_overall_task(page_task)
    cache.set(
        "purchased_all",
        list(map(lambda x: x.get("id"), output)),
        expire=of_env.getattr("RESPONSE_EXPIRY"),
    )
    return output


async def scrape_all_paid(c, offset=0, required=None):
    media = []
    new_tasks = []
    task = None
    url = of_env.getattr("purchased_contentALL").format(offset)

    try:
        task = progress_utils.api.add_job_task(
            f"scrape entire paid page offset={offset}", visible=True
        )
        async with c.requests_async(url) as r:
            if not (200 <= r.status < 300):
                return [], []

            data = await r.json_()
            media_lists = list(filter(lambda x: isinstance(x, list), data.values()))
            media = media_lists[0] if media_lists else []

            if not data.get("hasMore") or not bool(media):
                return media, new_tasks

            if required is None:
                new_tasks.append(
                    asyncio.create_task(scrape_all_paid(c, offset=offset + len(media)))
                )
            elif len(media) < required:
                new_tasks.append(
                    asyncio.create_task(
                        scrape_all_paid(
                            c,
                            offset=offset + len(media),
                            required=required - len(media),
                        )
                    )
                )

            return media, new_tasks

    except Exception as E:
        log.error(f"Scrape all paid failed at offset {offset}")
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        return [], []
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
