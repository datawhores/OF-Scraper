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
import  ofscraper.runner.manager as manager2
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
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

    tasks.append(asyncio.create_task(scrape_paid(c, username)))
    data = await process_tasks(tasks)
    update_check(data, model_id, None, API)
    return data


async def process_tasks(tasks):
    page_count = 0
    page_task = progress_utils.add_api_task(
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
                progress_utils.update_api_task(
                    page_task,
                    description=f"Paid Content Pages Progress: {page_count}",
                )
                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Paid')} {list(map(lambda x:x['id'],new_posts))}"
                )
                trace_progress_log(f"{API} tasks", new_posts)
                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks_batch

    progress_utils.remove_api_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Paid')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(f"{common_logs.FINAL_COUNT.format('Paid')} {len(responseArray)}")

    return responseArray


@run
async def scrape_paid(c, username, offset=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    media = None

    new_tasks = []
    url = constants.getattr("purchased_contentEP").format(offset, username)
    try:

        task = progress_utils.add_api_job_task(
            f"scrape paid offset -> {offset} username -> {username}",
            visible=True,
        )
        log.debug(f"trying access {API.lower()} posts with url:{url} offset:{offset}")

        async with c.requests_async(url) as r:

            data = await r.json_()
            log.debug(
                f"successfully access {API.lower()} posts with url:{url} offset:{offset}"
            )
            trace_progress_log(f"{API} all users requests", data)

            media = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            log.debug(f"offset:{offset} -> media found {len(media)}")
            log.debug(
                f"offset:{offset} -> hasmore value in json {data.get('hasMore','undefined') }"
            )
            log.debug(
                f"offset:{offset} -> found paid content ids {list(map(lambda x:x.get('id'),media))}"
            )
            if data.get("hasMore") and len(media) > 0:
                offset += len(media)
                new_tasks.append(
                    asyncio.create_task(scrape_paid(c, username, offset=offset))
                )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        progress_utils.remove_api_job_task(task)
    return media, new_tasks


@run
async def get_all_paid_posts():
    async with manager2.Manager.aget_ofsession(
        sem_count=constants.getattr("SCRAPE_PAID_SEMS"),
    ) as c:
        tasks = await create_tasks_scrape_paid(c)
        data= await process_tasks_all_paid(tasks)
        return create_all_paid_dict(data)


async def create_tasks_scrape_paid(c):
    min_posts = 80
    tasks = []
    allpaid = cache.get("purchased_all", default=[])
    log.debug(f"[bold]All Paid Cache[/bold] {len(allpaid)} found")

    if len(allpaid) > min_posts:
        splitArrays = [i for i in range(0, len(allpaid), min_posts)]
        [
            tasks.append(
                asyncio.create_task(
                    scrape_all_paid(
                        c,
                        required=min_posts,
                        offset=splitArrays[i],
                    )
                )
            )
            for i in range(0, len(splitArrays) - 1)
        ]
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
    allpaid = cache.get("purchased_all", default=[])
    log.debug(f"[bold]All Paid Cache[/bold] {len(allpaid)} found")
    page_task = progress_utils.add_api_task(
        f"[Scrape Paid] Pages Progress: {page_count}", visible=True
    )
    while tasks:
        new_tasks_batch = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks = await task
                new_tasks_batch.extend(new_tasks)
                page_count = page_count + 1
                progress_utils.update_api_task(
                    page_task,
                    description=f"[Scrape Paid] Pages Progress: {page_count}",
                )
                output.extend(result)
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('ALL Paid')} {list(map(lambda x:x['id'],result))}"
                )
                trace_progress_log(f"{API} all users tasks", result)
            except Exception as E:

                log.traceback_(E)
                log.traceback_(traceback.format_exc())
        tasks = new_tasks_batch
    progress_utils.remove_api_task(page_task)

    log.debug(f"[bold]Paid Post count with Dupes[/bold] {len(output)} found")
    trace_log_raw(f"{API} all users final", output, final_count=True)

    cache.set(
        "purchased_all",
        list(map(lambda x: x.get("id"), list(output))),
        expire=constants.getattr("RESPONSE_EXPIRY"),
    )
    # filter at user level
    return output



def create_all_paid_dict(paid_content):
    user_dict = {}
    for ele in paid_content:
        user_id = ele.get("fromUser", {}).get("id") or ele.get("author", {}).get("id")
        user_dict.setdefault(str(user_id), []).append(ele)
    [update_check(val, key, None, API) for key, val in user_dict.items()]
    return user_dict


async def scrape_all_paid(c, offset=0, required=None):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    media = None

    new_tasks = []
    url = constants.getattr("purchased_contentALL").format(offset)
    try:

        task = progress_utils.add_api_job_task(
            f"scrape entire paid page offset={offset}",
            visible=True,
        )

        async with c.requests_async(url) as r:

            log_id = f"offset {offset or 0}:"
            data = await r.json_()
            media = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            if not data.get("hasMore") or not bool(media):
                log.debug(f"{log_id} -> no paid posts found")
                return media, new_tasks
            log.debug(f"{log_id} -> number of post found {len(media)}")
            log.debug(
                f"{log_id} -> first date {media[0].get('createdAt') or media[0].get('postedAt')}"
            )
            log.debug(
                f"{log_id} -> last date {media[-1].get('createdAt') or media[-1].get('postedAt')}"
            )
            log.debug(
                f"{log_id} -> found paid content ids {list(map(lambda x:x.get('id'),media))}"
            )

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

    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
         progress_utils.remove_api_job_task(task)


def get_individual_paid_post(username, model_id, postid):
    data = get_paid_posts(username, model_id)
    postid = int(postid)
    posts = list(filter(lambda x: int(x["id"]) == postid, data))
    if len(posts) > 0:
        return posts[0]
    return None
