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

import ofscraper.api.common.logs as common_logs
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
from ofscraper.utils.context.run_async import run

paid_content_list_name = "list"
log = logging.getLogger("shared")


@run
async def get_paid_posts(username, model_id, c=None):
    tasks = []

    tasks.append(asyncio.create_task(scrape_paid(c, username)))
    data = await process_tasks(tasks, model_id)

    return data


async def process_tasks(tasks, model_id):
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
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Paid')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                new_posts,
                            )
                        )
                    )
                )

                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    progress_utils.remove_api_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Paid')} {list(map(lambda x:x['id'],responseArray))}"
    )

    paid_str = ""
    for post in responseArray:
        paid_str += f"{common_logs.RAW_INNER} {post}\n\n"
    log.trace(f"{common_logs.FINAL_RAW.format('Paid')}".format(posts=paid_str))
    log.debug(f"{common_logs.FINAL_COUNT.format('Paid')} {len(responseArray)}")
    set_check(model_id, responseArray)
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

        async with c.requests_async(url,forced=constants.getattr("API_FORCE_KEY")) as r:

            data = await r.json_()
            log.trace("paid raw {posts}".format(posts=data))

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
    data = await create_tasks_scrape_paid()
    return create_all_paid_dict(data)


async def create_tasks_scrape_paid():
    output = []
    min_posts = 80
    tasks = []
    page_count = 0
    async with sessionManager.sessionManager(
        sem=constants.getattr("SCRAPE_PAID_SEMS"),
        retries=constants.getattr("API_PAID_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
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

        page_task = progress_utils.add_api_task(
            f"[Scrape Paid] Pages Progress: {page_count}", visible=True
        )
        while tasks:
            new_tasks = []
            for task in asyncio.as_completed(tasks):
                try:
                    result, new_tasks_batch = await task
                    page_count = page_count + 1
                    progress_utils.update_api_task(
                        page_task,
                        description=f"[Scrape Paid] Pages Progress: {page_count}",
                    )
                    output.extend(result)
                    log.debug(
                        f"{common_logs.PROGRESS_IDS.format('ALL Paid')} {list(map(lambda x:x['id'],result))}"
                    )
                    paid_str = ""
                    for post in output:
                        paid_str += f"{common_logs.RAW_INNER} {post}\n\n"

                    log.trace(
                        f"{common_logs.PROGRESS_RAW.format('All Paid')}".format(
                            posts=paid_str
                        )
                    )
                    new_tasks.extend(new_tasks_batch)
                    
                except Exception as E:
                    
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
            tasks = new_tasks
        progress_utils.remove_api_task(page_task)

    log.debug(f"[bold]Paid Post count with Dupes[/bold] {len(output)} found")
    log.trace(
        "paid raw duped {posts}".format(
            posts="\n\n".join(map(lambda x: f"dupedinfo all paid: {str(x)}", output))
        )
    )
    cache.set(
        "purchased_all",
        list(map(lambda x: x.get("id"), list(output))),
        expire=constants.getattr("RESPONSE_EXPIRY"),
    )
    cache.close()
    # filter at user level
    return output


def create_all_paid_dict(paid_content):
    user_dict = {}
    for ele in paid_content:
        user_id = ele.get("fromUser", {}).get("id") or ele.get("author", {}).get("id")
        user_dict.setdefault(str(user_id), []).append(ele)
    [set_check(key, val) for key, val in user_dict.items()]
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

        async with c.requests_async(url,forced=constants.getattr("API_FORCE_KEY")) as r:

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


def set_check(model_id, unduped):
    seen = set()
    all_posts = [
        post
        for post in cache.get(f"purchase_check_{model_id}", default=[]) + unduped
        if post["id"] not in seen and not seen.add(post["id"])
    ]
    cache.set(
        f"purchased_check_{model_id}",
        all_posts,
        expire=constants.getattr("THREE_DAY_SECONDS"),
    )
    cache.close()


def get_individual_post(username, model_id, postid):
    data = get_paid_posts(username, model_id)
    postid = int(postid)
    posts = list(filter(lambda x: int(x["id"]) == postid, data))
    if len(posts) > 0:
        return posts[0]
    return None
