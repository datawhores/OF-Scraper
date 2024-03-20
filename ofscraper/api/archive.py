r"""
                                                             
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import contextvars
import logging
import math
import traceback

import arrow
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.db.operations as operations
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


sem = None


@run
async def get_archived_media(model_id, username, forced_after=None, c=None):
    tasks = []
    new_tasks = []
    min_posts = 50
    responseArray = []
    page_count = 0
    job_progress = progress_utils.archived_progress
    overall_progress = progress_utils.overall_progress

    # async with c or sessionbuilder.sessionBuilder(
    #     limit=constants.getattr("API_MAX_CONNECTION")
    # ) as c:
    oldarchived = (
        operations.get_archived_postinfo(model_id=model_id, username=username)
        if not read_args.retriveArgs().no_cache
        else []
    )

    log.trace(
        "oldarchive {posts}".format(
            posts="\n\n".join(list(map(lambda x: f"oldarchive: {str(x)}", oldarchived)))
        )
    )
    log.debug(f"[bold]Archived Cache[/bold] {len(oldarchived)} found")
    oldarchived = list(filter(lambda x: x != None, oldarchived))
    postedAtArray = sorted(oldarchived, key=lambda x: x[0])

    after = get_after(model_id, username, forced_after)
    # set check
    log.info(
        f"""
Setting initial archived scan date for {username} to {arrow.get(after).format('YYYY.MM.DD')}
[yellow]Hint: append ' --after 2000' to command to force scan of all archived posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --dupe' to command to force scan of all archived posts + download/re-download of all files[/yellow]
    """
    )
    filteredArray = (
        list(filter(lambda x: x[0] >= after, postedAtArray))
        if len(postedAtArray) > 0
        else []
    )

    if len(filteredArray) > min_posts:
        splitArrays = [
            filteredArray[i : i + min_posts]
            for i in range(0, len(filteredArray), min_posts)
        ]
        # use the previous split for timesamp
        tasks.append(
            asyncio.create_task(
                scrape_archived_posts(
                    c,
                    model_id,
                    job_progress=job_progress,
                    required_ids=set(list(map(lambda x: x[0], splitArrays[0]))),
                    timestamp=read_args.retriveArgs().after.float_timestamp
                    if read_args.retriveArgs().after
                    else None,
                )
            )
        )
        [
            tasks.append(
                asyncio.create_task(
                    scrape_archived_posts(
                        c,
                        model_id,
                        job_progress=job_progress,
                        required_ids=set(list(map(lambda x: x[0], splitArrays[i]))),
                        timestamp=splitArrays[i - 1][-1][0],
                    )
                )
            )
            for i in range(1, len(splitArrays) - 1)
        ]
        # keeping grabbing until nothing left
        tasks.append(
            asyncio.create_task(
                scrape_archived_posts(
                    c,
                    model_id,
                    job_progress=job_progress,
                    timestamp=splitArrays[-2][-1][0],
                )
            )
        )
    else:
        tasks.append(
            asyncio.create_task(
                scrape_archived_posts(
                    c, model_id, job_progress=job_progress, timestamp=after
                )
            )
        )

    page_task = overall_progress.add_task(
        f"Archived Content Pages Progress: {page_count}", visible=True
    )
    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * len(tasks)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        result, new_tasks_batch = await task
                        new_tasks.extend(new_tasks_batch)
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task,
                            description=f"Archived Content Pages Progress: {page_count}",
                        )
                        responseArray.extend(result)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
        except TimeoutError as E:
            cache.set(f"{model_id}_full_archived_scrape")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())

        tasks = new_tasks
    overall_progress.remove_task(page_task)
    progress_utils.archived_layout.visible = False

    unduped = {}
    log.debug(f"[bold]Archived Count with Dupes[/bold] {len(responseArray)} found")
    for post in responseArray:
        id = post["id"]
        if unduped.get(id):
            continue
        unduped[id] = post
    log.trace(f"archive dupeset postids {list(unduped.keys())}")
    log.trace(
        "archived raw unduped {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"undupedinfo archive: {str(x)}", unduped))
            )
        )
    )
    log.debug(f"[bold]Archived Count without Dupes[/bold] {len(unduped)} found")
    set_check(unduped, model_id, after)
    return list(unduped.values())


def set_check(unduped, model_id, after):
    if not after:
        newCheck = {}
        for post in cache.get(f"archived_check_{model_id}", default=[]) + list(
            unduped.values()
        ):
            newCheck[post["id"]] = post
        cache.set(
            f"archived_check_{model_id}",
            list(newCheck.values()),
            expire=constants.getattr("DAY_SECONDS"),
        )
        cache.close()


def get_after(model_id, username, forced_after=None):
    if forced_after != None:
        return forced_after
    elif read_args.retriveArgs().after == 0:
        return 0
    elif read_args.retriveArgs().after:
        return read_args.retriveArgs().after.float_timestamp

    elif (
        cache.get(f"{model_id}_full_archived_scrape")
        and not read_args.retriveArgs().after
        and not data.get_disable_after()
    ):
        log.info(
            "Used --after previously. Scraping all archived posts required to make sure content is not missing"
        )
        return 0
    curr = operations.get_archived_postinfo(model_id=model_id, username=username)

    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
        return 0
    missing_items = list(filter(lambda x: x[-2] == 0, curr))
    missing_items = list(sorted(missing_items, key=lambda x: arrow.get(x[-1])))
    if len(missing_items) == 0:
        log.debug("Using last db date because,all downloads in db marked as downloaded")
        return (
            operations.get_last_archived_date(model_id=model_id, username=username)
            - 1000
        )
    else:
        log.debug(
            f"Setting date slightly before earliest missing item\nbecause {len(missing_items)} posts in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0][-1]).float_timestamp - 1000


@run
async def scrape_archived_posts(
    c, model_id, job_progress=None, timestamp=None, required_ids=None
) -> list:
    global sem
    posts = None
    attempt.set(0)
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))
    if timestamp and (
        float(timestamp)
        > (read_args.retriveArgs().before or arrow.now()).float_timestamp
    ):
        return []
    if timestamp:
        ep = constants.getattr("archivedNextEP")
        url = ep.format(model_id, str(timestamp))
    else:
        ep = constants.getattr("archivedEP")
        url = ep.format(model_id)
    log.debug(url)

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
            new_tasks = []
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                task = (
                    job_progress.add_task(
                        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')}: Timestamp -> {arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}",
                        visible=True,
                    )
                    if job_progress
                    else None
                )
                async with c.requests(url)() as r:
                    if r.ok:
                        posts = (await r.json_())["list"]
                        log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}"
                        if not posts:
                            posts = []
                        if len(posts) == 0:
                            log.debug(f" {log_id} -> number of post found 0")
                        elif len(posts) > 0:
                            log.debug(
                                f"{log_id} -> number of archived post found {len(posts)}"
                            )
                            log.debug(
                                f"{log_id} -> first date {posts[0].get('createdAt') or posts[0].get('postedAt')}"
                            )
                            log.debug(
                                f"{log_id} -> last date {posts[-1].get('createdAt') or posts[-1].get('postedAt')}"
                            )
                            log.debug(
                                f"{log_id} -> found archived post IDs {list(map(lambda x:x.get('id'),posts))}"
                            )
                            log.trace(
                                "{log_id} -> archive raw {posts}".format(
                                    log_id=log_id,
                                    posts="\n\n".join(
                                        list(
                                            map(
                                                lambda x: f"scrapeinfo archive: {str(x)}",
                                                posts,
                                            )
                                        )
                                    ),
                                )
                            )

                            if required_ids == None:
                                new_tasks.append(
                                    asyncio.create_task(
                                        scrape_archived_posts(
                                            c,
                                            model_id,
                                            job_progress=None,
                                            timestamp=posts[-1]["postedAtPrecise"],
                                        )
                                    )
                                )
                            else:
                                [
                                    required_ids.discard(float(ele["postedAtPrecise"]))
                                    for ele in posts
                                ]

                                if len(required_ids) > 0 and float(
                                    timestamp or 0
                                ) < max(required_ids):
                                    new_tasks.append(
                                        asyncio.create_task(
                                            scrape_archived_posts(
                                                c,
                                                model_id,
                                                job_progress=None,
                                                timestamp=posts[-1]["postedAtPrecise"],
                                                required_ids=required_ids,
                                            )
                                        )
                                    )
                    else:
                        log.debug(
                            f"[bold]archived response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]archived response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]archived headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task) if job_progress and task else None
            return posts, new_tasks
