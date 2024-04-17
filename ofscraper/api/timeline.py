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

import ofscraper.api.common.logs as common_logs
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.db.operations as operations
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


@run
async def get_timeline_posts_progress(model_id, username, forced_after=None, c=None):

    after = await get_after(model_id, username, forced_after)

    splitArrays = await get_split_array(model_id, username, after)
    tasks = get_tasks(splitArrays, c, model_id, after)
    data = await process_tasks(tasks, model_id, after)
    progress_utils.timeline_layout.visible = False
    return data


@run
async def get_timeline_posts(model_id, username, forced_after=None, c=None):
    if not read_args.retriveArgs().no_cache:
        oldtimeline = await operations.get_timeline_postsinfo(
            model_id=model_id, username=username
        )
    else:
        oldtimeline = []
    log.trace(
        "oldtimeline {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"oldtimeline: {str(x)}", oldtimeline))
            )
        )
    )
    log.debug(f"[bold]Timeline Cache[/bold] {len(oldtimeline)} found")
    oldtimeline = list(filter(lambda x: x != None, oldtimeline))
    after = await get_after(model_id, username, forced_after)

    with progress_utils.set_up_api_timeline():
        splitArrays = await get_split_array(model_id, username, after)
        tasks = get_tasks(splitArrays, c, model_id, after)
        return await process_tasks(tasks, model_id, after)


async def process_tasks(tasks, model_id, after):
    responseArray = []
    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
        f" Timeline Content Pages Progress: {page_count}", visible=True
    )
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
                        description=f"Timeline Content Pages Progress: {page_count}",
                    )
                    new_posts = [
                        post
                        for post in result
                        if post["id"] not in seen and not seen.add(post["id"])
                    ]
                    log.debug(
                        f"{common_logs.PROGRESS_IDS.format('Timeline')} {list(map(lambda x:x['id'],new_posts))}"
                    )
                    log.trace(
                        f"{common_logs.PROGRESS_RAW.format('Timeline')}".format(
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
        f"{common_logs.FINAL_IDS.format('Timeline')} {list(map(lambda x:x['id'],responseArray))}"
    )
    log.trace(
        f"{common_logs.FINAL_RAW.format('Timeline')}".format(
            posts="\n\n".join(
                list(map(lambda x: f"{common_logs.RAW_INNER} {x}", responseArray))
            )
        )
    )
    log.debug(f"{common_logs.FINAL_COUNT.format('Timeline')} {len(responseArray)}")

    return responseArray


async def get_split_array(model_id, username, after):
    min_posts = 50

    if not read_args.retriveArgs().no_cache:
        oldtimeline = await operations.get_timeline_postsinfo(
            model_id=model_id, username=username
        )
    else:
        oldtimeline = []
    log.trace(
        "oldtimeline {posts}".format(
            posts="\n\n".join(
                list(map(lambda x: f"oldtimeline: {str(x)}", oldtimeline))
            )
        )
    )
    log.debug(f"[bold]Timeline Cache[/bold] {len(oldtimeline)} found")
    oldtimeline = list(filter(lambda x: x is not None, oldtimeline))
    postsDataArray = sorted(oldtimeline, key=lambda x: x.get("created_at"))
    log.info(
        f"""
Setting initial timeline scan date for {username} to {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))}
[yellow]Hint: append ' --after 2000' to command to force scan of all timeline posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all timeline posts + download/re-download of all files[/yellow]

            """
    )
    filteredArray = list(filter(lambda x: x.get("created_at") >= after, postsDataArray))

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]
    return splitArrays


def get_tasks(splitArrays, c, model_id, after):
    tasks = []
    job_progress = progress_utils.timeline_progress

    if len(splitArrays) > 2:
        tasks.append(
            asyncio.create_task(
                scrape_timeline_posts(
                    c,
                    model_id,
                    job_progress=job_progress,
                    required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
                    timestamp=splitArrays[0][0].get("created_at"),
                    offset=True,
                )
            )
        )
        [
            tasks.append(
                asyncio.create_task(
                    scrape_timeline_posts(
                        c,
                        model_id,
                        job_progress=job_progress,
                        required_ids=set(
                            [ele.get("created_at") for ele in splitArrays[i]]
                        ),
                        timestamp=splitArrays[i - 1][-1].get("created_at"),
                        offset=False,
                    )
                )
            )
            for i in range(1, len(splitArrays) - 1)
        ]
        # keeping grabbing until nothing left
        tasks.append(
            asyncio.create_task(
                scrape_timeline_posts(
                    c,
                    model_id,
                    job_progress=job_progress,
                    timestamp=splitArrays[-1][0].get("created_at"),
                    offset=True,
                )
            )
        )
    # use the first split if less then 3
    elif len(splitArrays) > 0:
        tasks.append(
            asyncio.create_task(
                scrape_timeline_posts(
                    c,
                    model_id,
                    job_progress=job_progress,
                    timestamp=splitArrays[0][0].get("created_at"),
                    offset=True,
                )
            )
        )
    # use after if split is empty i.e no db data
    else:
        tasks.append(
            asyncio.create_task(
                scrape_timeline_posts(
                    c, model_id, job_progress=job_progress, timestamp=after, offset=True
                )
            )
        )
    return tasks


def set_check(unduped, model_id, after):
    if not after:
        seen = set()
        all_posts = [
            post
            for post in cache.get(f"timeline_check_{model_id}", default=[]) + unduped
            if post["id"] not in seen and not seen.add(post["id"])
        ]
        cache.set(
            f"timeline_check_{model_id}",
            all_posts,
            expire=constants.getattr("DAY_SECONDS"),
        )
        cache.close()


def get_individual_post(id):
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
    ) as c:
        with c.requests(constants.getattr("INDIVIDUAL_TIMELINE").format(id)) as r:
            log.trace(f"post raw individual {r.json()}")
            return r.json()


async def get_after(model_id, username, forced_after=None):
    if forced_after is not None:
        return forced_after
    elif not settings.get_after_enabled():
        return 0
    elif read_args.retriveArgs().after == 0:
        return 0
    elif read_args.retriveArgs().after:
        return read_args.retriveArgs().after.float_timestamp
    elif cache.get(f"{model_id}_full_timeline_scrape"):
        log.info(
            "Used --after previously. Scraping all timeline posts required to make sure content is not missing"
        )
        return 0
    curr = await operations.get_timeline_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
        return 0
    missing_items = list(filter(lambda x: x.get("downloaded") != 1, curr))
    missing_items = list(
        sorted(missing_items, key=lambda x: arrow.get(x.get("posted_at") or 0))
    )
    if len(missing_items) == 0:
        log.debug("Using last db date because,all downloads in db marked as downloaded")
        return await operations.get_last_timeline_date(
            model_id=model_id, username=username
        )
    else:
        log.debug(
            f"Setting date slightly before earliest missing item\nbecause {len(missing_items)} posts in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0]["posted_at"] or 0).float_timestamp


async def scrape_timeline_posts(
    c, model_id, job_progress=None, timestamp=None, required_ids=None, offset=False
) -> list:
    posts = None
    attempt.set(0)
    timestamp = float(timestamp) - 1000 if timestamp and offset else timestamp

    if timestamp and (
        float(timestamp)
        > (read_args.retriveArgs().before or arrow.now()).float_timestamp
    ):
        return [], []
    url = (
        constants.getattr("timelineNextEP").format(model_id, str(timestamp))
        if timestamp
        else constants.getattr("timelineEP").format(model_id)
    )
    log.debug(url)
    await asyncio.sleep(1)
    new_tasks = []
    try:
        attempt.set(attempt.get(0) + 1)
        task = (
            job_progress.add_task(
                f"Attempt {attempt.get()}/{constants.getattr('API_NUM_TRIES')}: Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp!=None  else 'initial'}",
                visible=True,
            )
            if job_progress
            else None
        )

        async with c.requests_async(url=url) as r:
            posts = (await r.json_())["list"]
            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp!=None  else 'initial'}"
            if not posts:
                posts = []
            if len(posts) == 0:
                log.debug(f"{log_id} -> number of post found 0")

            elif len(posts) > 0:
                log.debug(f"{log_id} -> number of post found {len(posts)}")
                log.debug(
                    f"{log_id} -> first date {posts[0].get('createdAt') or posts[0].get('postedAt')}"
                )
                log.debug(
                    f"{log_id} -> last date {posts[-1].get('createdAt') or posts[-1].get('postedAt')}"
                )
                log.debug(
                    f"{log_id} -> found postids {list(map(lambda x:x.get('id'),posts))}"
                )
                log.trace(
                    "{log_id} -> post raw {posts}".format(
                        log_id=log_id,
                        posts="\n\n".join(
                            list(
                                map(
                                    lambda x: f"scrapeinfo timeline: {str(x)}",
                                    posts,
                                )
                            )
                        ),
                    )
                )
                if not required_ids:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_timeline_posts(
                                c,
                                model_id,
                                job_progress=job_progress,
                                timestamp=posts[-1]["postedAtPrecise"],
                                offset=False,
                            )
                        )
                    )
                else:
                    [
                        required_ids.discard(float(ele["postedAtPrecise"]))
                        for ele in posts
                    ]
                    if len(required_ids) > 0 and float((timestamp) or 0) <= max(
                        required_ids
                    ):
                        new_tasks.append(
                            asyncio.create_task(
                                scrape_timeline_posts(
                                    c,
                                    model_id,
                                    job_progress=job_progress,
                                    timestamp=posts[-1]["postedAtPrecise"],
                                    required_ids=required_ids,
                                    offset=False,
                                )
                            )
                        )
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        (job_progress.remove_task(task) if job_progress and task != None else None)
    return posts, new_tasks
