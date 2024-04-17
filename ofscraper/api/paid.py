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
import contextvars
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor

import ofscraper.api.common.logs as common_logs
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
from ofscraper.utils.context.run_async import run

paid_content_list_name = "list"
log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


@run
async def get_paid_posts_progress(username, model_id, c=None):
    tasks = []

    job_progress = progress_utils.paid_progress
    tasks.append(
        asyncio.create_task(scrape_paid(c, username, job_progress=job_progress))
    )
    data = await process_tasks(tasks, model_id)

    progress_utils.paid_layout.visible = False
    return data


@run
async def get_paid_posts(model_id, username, c=None):
    tasks = []
    with progress_utils.set_up_api_paid():
        job_progress = progress_utils.paid_progress
        tasks.append(
            asyncio.create_task(scrape_paid(c, username, job_progress=job_progress))
        )
        return await process_tasks(tasks, model_id)


async def process_tasks(tasks, model_id):
    page_count = 0
    overall_progress = progress_utils.overall_progress
    page_task = overall_progress.add_task(
        f"Paid Content Pages Progress: {page_count}", visible=True
    )
    responseArray = []
    seen = set()

    while tasks:
        new_tasks = []
        try:
            for task in asyncio.as_completed(
                tasks, timeout=constants.getattr("API_TIMEOUT_PER_TASK")
            ):
                try:
                    result, new_tasks_batch = await task
                    new_tasks.extend(new_tasks_batch)
                    page_count = page_count + 1
                    overall_progress.update(
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
                                list(
                                    map(
                                        lambda x: f"{common_logs.RAW_INNER} {x}",
                                        new_posts,
                                    )
                                )
                            )
                        )
                    )

                    responseArray.extend(new_posts)
                except asyncio.TimeoutError:
                    log.traceback_("Task timed out")
                    log.traceback_(traceback.format_exc())
                    [ele.cancel() for ele in tasks]
                    break
                except Exception as E:
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    continue
        except asyncio.TimeoutError:
            log.traceback_("Task timed out")
            log.traceback_(traceback.format_exc())
            [ele.cancel() for ele in tasks]
        tasks = new_tasks

    overall_progress.remove_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Paid')} {list(map(lambda x:x['id'],responseArray))}"
    )
    log.trace(
        f"{common_logs.FINAL_RAW.format('Paid')}".format(
            posts="\n\n".join(
                list(map(lambda x: f"{common_logs.RAW_INNER} {x}", responseArray))
            )
        )
    )
    log.debug(f"{common_logs.FINAL_COUNT.format('Paid')} {len(responseArray)}")
    set_check(responseArray, model_id)
    return responseArray


def set_check(unduped, model_id):
    seen = set()
    all_posts = [
        post
        for post in cache.get(f"purchase_check_{model_id}", default=[]) + unduped
        if post["id"] not in seen and not seen.add(post["id"])
    ]
    cache.set(
        f"purchased_check_{model_id}",
        all_posts,
        expire=constants.getattr("DAY_SECONDS"),
    )
    cache.close()


@run
async def scrape_paid(c, username, job_progress=None, offset=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    media = None

    attempt.set(0)
    await asyncio.sleep(1)

    new_tasks = []
    try:
        attempt.set(attempt.get(0) + 1)
        task = (
            (
                job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('API_NUM_TRIES')} scrape paid offset -> {offset} username -> {username}",
                    visible=True,
                )
                if job_progress
                else None
            )
            if job_progress
            else None
        )

        async with c.requests_async(
            url=constants.getattr("purchased_contentEP").format(offset, username)
        ) as r:
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
                    asyncio.create_task(
                        scrape_paid(c, username, job_progress, offset=offset)
                    )
                )
            (job_progress.remove_task(task) if task and job_progress else None)
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task) if task and job_progress else None

    return media, new_tasks


@run
async def get_all_paid_posts():
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        output = []
        min_posts = 100
        tasks = []
        page_count = 0
        with progress_utils.setup_all_paid_live():
            job_progress = progress_utils.all_paid_progress
            overall_progress = progress_utils.overall_progress
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
                    # use the previous split for timesamp
                    tasks.append(
                        asyncio.create_task(
                            scrape_all_paid(
                                c, job_progress, offset=0, count=0, required=0
                            )
                        )
                    )
                    [
                        tasks.append(
                            asyncio.create_task(
                                scrape_all_paid(
                                    c,
                                    job_progress,
                                    count=0,
                                    required=0,
                                    offset=splitArrays[i],
                                )
                            )
                        )
                        for i in range(1, len(splitArrays))
                    ]
                    # keeping grabbing until nothign left
                    tasks.append(
                        asyncio.create_task(
                            scrape_all_paid(c, job_progress, offset=len(allpaid))
                        )
                    )
                else:
                    tasks.append(asyncio.create_task(scrape_all_paid(c, job_progress)))

                page_task = overall_progress.add_task(
                    f" Pages Progress: {page_count}", visible=True
                )
                while tasks:
                    new_tasks = []
                    for task in asyncio.as_completed(
                        tasks, timeout=constants.getattr("API_TIMEOUT_PER_TASK")
                    ):
                        try:
                            result, new_tasks_batch = await task
                            page_count = page_count + 1
                            overall_progress.update(
                                page_task, description=f"Pages Progress: {page_count}"
                            )
                            output.extend(result)
                            log.debug(
                                f"{common_logs.PROGRESS_IDS.format('ALL Paid')} {list(map(lambda x:x['id'],result))}"
                            )
                            log.trace(
                                f"{common_logs.PROGRESS_RAW.format('All Paid')}".format(
                                    posts="\n\n".join(
                                        list(
                                            map(
                                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                                result,
                                            )
                                        )
                                    )
                                )
                            )
                            new_tasks.extend(new_tasks_batch)
                            await asyncio.sleep(1)
                        except Exception as E:
                            await asyncio.sleep(1)
                            log.debug(E)
                            continue
                    tasks = new_tasks
                overall_progress.remove_task(page_task)

        log.debug(f"[bold]Paid Post count with Dupes[/bold] {len(output)} found")
        log.trace(
            "paid raw duped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"dupedinfo all paid: {str(x)}", output))
                )
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


async def scrape_all_paid(c, job_progress=None, offset=0, count=0, required=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    media = None

    attempt.set(0)
    await asyncio.sleep(1)
    new_tasks = []
    try:
        attempt.set(attempt.get(0) + 1)
        task = job_progress.add_task(
            f"Attempt {attempt.get()}/{constants.getattr('API_NUM_TRIES')} scrape entire paid page offset={offset}",
            visible=True,
        )

        async with c.requests_async(
            url=constants.getattr("purchased_contentALL").format(offset)
        ) as r:
            log_id = f"offset {offset or 0}:"
            data = await r.json_()
            media = list(filter(lambda x: isinstance(x, list), data.values()))[0]
            if not data.get("hasMore"):
                media = []
            if not media:
                media = []
            if len(media) == 0:
                log.debug(f"{log_id} -> number of post found 0")
            elif len(media) > 0:
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

                if required == 0:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_all_paid(c, job_progress, offset=offset + len(media))
                        )
                    )

                elif len(count) < len(required):
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_all_paid(
                                c,
                                job_progress,
                                offset=offset + len(media),
                                required=required,
                                count=count + len(media),
                            )
                        )
                    )

    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task)

    return media, new_tasks


def get_individual_post(username, model_id, postid):
    data = get_paid_posts_progress(username, model_id)
    postid = int(postid)
    posts = list(filter(lambda x: int(x["id"]) == postid, data))
    if len(posts) > 0:
        return posts[0]
    return None
