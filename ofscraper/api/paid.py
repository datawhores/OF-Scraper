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

from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.sems as sems
from ofscraper.utils.context.run_async import run

paid_content_list_name = "list"
log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
sem = None


@run
async def get_paid_posts_progress(username, model_id, c=None):
    global sem
    sem = sems.get_req_sem()
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
    global sem
    sem = sems.get_req_sem()
    tasks = []

    # async with c or sessionbuilder.sessionBuilder(
    #     limit=constants.getattr("API_MAX_CONNECTION")
    # ) as c:
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
    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * max(len(tasks), 2)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        result, new_tasks_batch = await task
                        new_tasks.extend(new_tasks_batch)
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task,
                            description=f"Paid Content Pages Progress: {page_count}",
                        )
                        responseArray.extend(result)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
        except TimeoutError as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        tasks = new_tasks
    overall_progress.remove_task(page_task)
    log.debug(f"[bold]Paid Count with Dupes[/bold] {len(responseArray)} found")

    seen = set()
    new_posts = [
        post
        for post in responseArray
        if post["id"] not in seen and not seen.add(post["id"])
    ]

    log.trace(f"paid postids {list(map(lambda x:x.get('id'),new_posts))}")

    log.trace(
        "paid raw unduped {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"undupedinfo paid: {str(x)}", new_posts))
            )
        )
    )
    log.debug(f"[bold]Paid Count without Dupes[/bold] {len(new_posts)} found")

    set_check(new_posts, model_id)
    return new_posts


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
    global sem
    media = None

    attempt.set(0)

    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            await asyncio.sleep(1)

            new_tasks = []
            try:
                attempt.set(attempt.get(0) + 1)
                task = (
                    (
                        job_progress.add_task(
                            f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} scrape paid offset -> {offset} username -> {username}",
                            visible=True,
                        )
                        if job_progress
                        else None
                    )
                    if job_progress
                    else None
                )

                async with c.requests(
                    url=constants.getattr("purchased_contentEP").format(
                        offset, username
                    )
                )() as r:
                    if r.ok:
                        data = await r.json_()
                        log.trace("paid raw {posts}".format(posts=data))

                        media = list(
                            filter(lambda x: isinstance(x, list), data.values())
                        )[0]
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
                                    scrape_paid(
                                        c, username, job_progress, offset=offset
                                    )
                                )
                            )
                        (
                            job_progress.remove_task(task)
                            if task and job_progress
                            else None
                        )

                    else:
                        log.debug(f"[bold]paid response status code:[/bold]{r.status}")
                        log.debug(f"[bold]paid response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]paid headers:[/bold] {r.headers}")
                        job_progress.remove_task(task)
                        r.raise_for_status()
            except Exception as E:
                await asyncio.sleep(1)
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task) if task and job_progress else None

        return media, new_tasks


@run
async def get_all_paid_posts():
    global sem
    sem = sems.get_req_sem()
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        output = []
        min_posts = 100
        tasks = []
        page_count = 0
        with progress_utils.setup_all_paid_live():
            job_progress = progress_utils.all_paid_progress
            overall_progress = progress_utils.overall_progress

            async with sessionbuilder.sessionBuilder() as c:
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
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    tasks = list(pending)
                    await asyncio.sleep(1)
                    for result in done:
                        try:
                            result, new_tasks = await result
                            page_count = page_count + 1
                            overall_progress.update(
                                page_task, description=f"Pages Progress: {page_count}"
                            )
                            output.extend(result)
                            tasks.extend(new_tasks)
                            await asyncio.sleep(1)
                        except Exception as E:
                            await asyncio.sleep(1)
                            log.debug(E)
                            continue

                overall_progress.remove_task(page_task)

        log.debug(f"[bold]Paid Post count with Dupes[/bold] {len(output)} found")
        log.trace(
            "paid raw duped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"dupedinfo all paid: {str(x)}", output))
                )
            )
        )
        seen = set()
        new_posts = [
            post
            for post in output
            if post["id"] not in seen and not seen.add(post["id"])
        ]
        log.trace(f"all paid postids {list(map(lambda x:x.get('id'),new_posts))}")
        log.debug(f"[bold]Paid Post count without Dupes[/bold] {len(new_posts)} found")
        log.trace(
            "paid raw duped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"undupedinfo all paid: {str(x)}", new_posts))
                )
            )
        )
        cache.set(
            "purchased_all",
            list(map(lambda x: x.get("id"), list())),
            expire=constants.getattr("RESPONSE_EXPIRY"),
        )
        cache.close()
        # filter at user level
        return output


async def scrape_all_paid(c, job_progress=None, offset=0, count=0, required=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    global sem
    media = None

    attempt.set(0)
    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            await asyncio.sleep(1)
            new_tasks = []
            try:
                attempt.set(attempt.get(0) + 1)
                task = job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} scrape entire paid page offset={offset}",
                    visible=True,
                )

                async with c.requests(
                    url=constants.getattr("purchased_contentALL").format(offset)
                )() as r:
                    if r.ok:
                        log_id = f"offset {offset or 0}:"
                        data = await r.json_()
                        media = list(
                            filter(lambda x: isinstance(x, list), data.values())
                        )[0]
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
                                        scrape_all_paid(
                                            c, job_progress, offset=offset + len(media)
                                        )
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

                    else:
                        log.debug(f"[bold]paid response status code:[/bold]{r.status}")
                        log.debug(f"[bold]paid response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]paid headers:[/bold] {r.headers}")
                        job_progress.remove_task(task)
                        r.raise_for_status()
            except Exception as E:
                await asyncio.sleep(1)
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

            return media, new_tasks


def get_individual_post(username, model_id, postid):
    data = get_paid_posts_progress(username, model_id)
    postid = int(postid)
    posts = list(filter(lambda x: int(x["id"]) == postid, data))
    if len(posts) > 0:
        return posts[0]
    return None
