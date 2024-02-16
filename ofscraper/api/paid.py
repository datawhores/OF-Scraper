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

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

paid_content_list_name = "list"
log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
sem = None


@run
async def get_paid_posts(username, model_id):
    global sem
    sem = semaphoreDelayed(constants.getattr("MAX_SEMAPHORE"))

    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting paid media...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        global tasks
        global new_tasks
        tasks = []
        new_tasks = []

        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionbuilder.sessionBuilder() as c:
                tasks.append(
                    asyncio.create_task(scrape_paid(c, username, job_progress))
                )

                page_task = overall_progress.add_task(
                    f" Pages Progress: {page_count}", visible=True
                )
                while tasks:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for result in done:
                        try:
                            result = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        output.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
                overall_progress.remove_task(page_task)
        outdict = {}
        for post in output:
            outdict[post["id"]] = post
        log.trace(
            "paid raw unduped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"undupedinfo paid: {str(x)}", outdict.values()))
                )
            )
        )
        set_check(outdict, model_id)
        return list(outdict.values())


def set_check(unduped, model_id):
    newCheck = {}
    for post in cache.get(f"purchased_check_{model_id}", default=[]) + list(unduped.values()):
        newCheck[post["id"]] = post
    cache.set(
        f"purchased_check_{model_id}",
        list(newCheck.values()),
        expire=constants.getattr("DAY_SECONDS"),
    )
    cache.close()


async def scrape_paid(c, username, job_progress, offset=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    global sem
    global tasks
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
            try:
                attempt.set(attempt.get(0) + 1)
                task = job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} scrape paid offset -> {offset} username -> {username}",
                    visible=True,
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
                        if data.get("hasMore"):
                            offset += len(media)
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_paid(
                                        c, username, job_progress, offset=offset
                                    )
                                )
                            )
                        job_progress.remove_task(task)

                    else:
                        log.debug(f"[bold]paid response status code:[/bold]{r.status}")
                        log.debug(f"[bold]paid response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]paid headers:[/bold] {r.headers}")
                        job_progress.remove_task(task)
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

        return media


@run
async def get_all_paid_posts():
    global sem
    sem = semaphoreDelayed(constants.getattr("MAX_SEMAPHORE"))
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting all paid media...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        min_posts = 100
        global tasks
        global new_tasks
        tasks = []
        new_tasks = []
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionbuilder.sessionBuilder() as c:
                allpaid = cache.get(f"purchased_all", default=[])
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
                    for result in done:
                        try:
                            result = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        output.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
                overall_progress.remove_task(page_task)
        outdict = {}
        log.debug(f"[bold]Paid Post count with Dupes[/bold] {len(output)} found")
        for post in output:
            outdict[post["id"]] = post

        log.debug(f"[bold]Paid Post count[/bold] {len(outdict.values())} found")
        cache.set(
            f"purchased_all",
            list(map(lambda x: x.get("id"), list(outdict.values()))),
            expire=constants.getattr("RESPONSE_EXPIRY"),
        )
        cache.close()
        # filter at user level
        return output


async def scrape_all_paid(c, job_progress, offset=0, count=0, required=0):
    """Takes headers to access onlyfans as an argument and then checks the purchased content
    url to look for any purchased content. If it finds some it will return it as a list.
    """
    global sem
    global new_tasks
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
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

            return media


def get_individual_post(username, model_id, postid):
    data = get_paid_posts(username, model_id)
    postid = int(postid)
    posts = list(filter(lambda x: int(x["id"]) == postid, data))
    if len(posts) > 0:
        return posts[0]
    return None
