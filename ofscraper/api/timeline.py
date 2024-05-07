r"""
                                                             
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
                 \/     \/           \/            \/         
"""

import asyncio
import logging
import math
import traceback

import arrow

import ofscraper.api.common.logs as common_logs
import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import get_timeline_media
from ofscraper.db.operations_.posts import (
    get_timeline_posts_info,
    get_youngest_timeline_date,
)
from ofscraper.utils.context.run_async import run
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")


@run
async def get_timeline_posts_progress(model_id, username, forced_after=None, c=None):

    after = await get_after(model_id, username, forced_after)
    after_log(username, after)
    splitArrays = await get_split_array(model_id, username, after)
    tasks = get_tasks(splitArrays, c, model_id, after)
    data = await process_tasks(tasks)
    progress_utils.timeline_layout.visible = False
    return data


@run
async def get_timeline_posts(model_id, username, forced_after=None, c=None):
    if not settings.get_api_cache_disabled():
        oldtimeline = await get_timeline_posts_info(
            model_id=model_id, username=username
        )
    else:
        oldtimeline = []
    trace_log_old(oldtimeline)

    log.debug(f"[bold]Timeline Cache[/bold] {len(oldtimeline)} found")
    oldtimeline = list(filter(lambda x: x is not None, oldtimeline))
    after = await get_after(model_id, username, forced_after)
    after_log(username, after)

    with progress_utils.set_up_api_timeline():
        splitArrays = await get_split_array(model_id, username, after)
        tasks = get_tasks(splitArrays, c, model_id, after)
        return await process_tasks(tasks)


async def process_tasks(tasks):
    responseArray = []
    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
        f" Timeline Content Pages Progress: {page_count}", visible=True
    )
    seen = set()
    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
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
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    overall_progress.remove_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Timeline')} {list(map(lambda x:x['id'],responseArray))}"
    )
    log.debug(f"{common_logs.FINAL_COUNT.format('Timeline')} {len(responseArray)}")

    trace_log_task(responseArray)
    return responseArray


async def get_oldtimeline(model_id, username):
    if not settings.get_api_cache_disabled():
        oldtimeline = await get_timeline_posts_info(
            model_id=model_id, username=username
        )
    else:
        oldtimeline = []
    oldtimeline = list(filter(lambda x: x is not None, oldtimeline))
    # dedupe oldtimeline
    seen = set()
    oldtimeline = [
        post
        for post in oldtimeline
        if post["post_id"] not in seen and not seen.add(post["post_id"])
    ]
    log.debug(f"[bold]Timeline Cache[/bold] {len(oldtimeline)} found")
    trace_log_old(oldtimeline)
    return oldtimeline


async def get_split_array(model_id, username, after):

    oldtimeline = await get_oldtimeline(model_id, username)
    if len(oldtimeline) == 0:
        return []
    min_posts = max(
        len(oldtimeline) // constants.getattr("REASONABLE_MAX_PAGE"),
        constants.getattr("MIN_PAGE_POST_COUNT"),
    )
    postsDataArray = sorted(oldtimeline, key=lambda x: arrow.get(x["created_at"]))
    filteredArray = list(filter(lambda x: bool(x["created_at"]), postsDataArray))
    filteredArray = list(
        filter(
            lambda x: arrow.get(x["created_at"]).float_timestamp >= after, filteredArray
        )
    )

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
            expire=constants.getattr("THREE_DAY_SECONDS"),
        )
        cache.close()


def get_individual_post(id):
    with sessionManager.sessionManager(
        backend="httpx",
        retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
        wait_min=constants.getattr("OF_MIN_WAIT_API"),
        wait_max=constants.getattr("OF_MAX_WAIT_API"),
        new_request_auth=True,
    ) as c:
        with c.requests(constants.getattr("INDIVIDUAL_TIMELINE").format(id)) as r:
            log.trace(f"post raw individual {r.json()}")
            return r.json()


async def get_after(model_id, username, forced_after=None):
    if forced_after is not None:
        return forced_after
    elif read_args.retriveArgs().after:
        return read_args.retriveArgs().after.float_timestamp
    elif read_args.retriveArgs().after == 0:
        return 0
    elif not settings.get_after_enabled():
        return 0
    elif cache.get(f"{model_id}_full_timeline_scrape"):
        log.info(
            "Used --after previously. Scraping all timeline posts required to make sure content is not missing"
        )
        return 0
    curr = await get_timeline_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting oldest date to zero because database is empty")
        return 0
    missing_items = list(
        filter(lambda x: x.get("downloaded") != 1 and x.get("unlocked") != 0, curr)
    )
    missing_items = list(sorted(missing_items, key=lambda x: arrow.get(x["posted_at"])))
    if len(missing_items) == 0:
        log.debug(
            "Using using newest db date, because all downloads in db marked as downloaded"
        )
        return arrow.get(
            await get_youngest_timeline_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        log.debug(
            f"Setting date slightly before oldest missing item\nbecause {len(missing_items)} posts in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0]["posted_at"]).float_timestamp


async def scrape_timeline_posts(
    c, model_id, job_progress=None, timestamp=None, required_ids=None, offset=False
) -> list:
    posts = None
    timestamp = float(timestamp) - 100 if timestamp and offset else timestamp

    url = (
        constants.getattr("timelineNextEP").format(model_id, str(timestamp))
        if timestamp
        else constants.getattr("timelineEP").format(model_id)
    )
    log.debug(url)
    new_tasks = []
    tasks = None

    await asyncio.sleep(1)

    try:
        task = (
            job_progress.add_task(
                f"Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}",
                visible=True,
            )
            if job_progress
            else None
        )

        async with c.requests_async(url=url) as r:
            posts = (await r.json_())["list"]
            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"
            if not bool(posts):
                log.debug(f"{log_id} -> no posts found")
                return [], []

            log.debug(f"{log_id} -> number of post found {len(posts)}")
            log.debug(
                f"{log_id} -> first date {arrow.get(posts[0].get('createdAt') or posts[0].get('postedAt')).format(constants.getattr('API_DATE_FORMAT'))}"
            )
            log.debug(
                f"{log_id} -> last date {arrow.get(posts[-1].get('createdAt') or posts[-1].get('postedAt')).format(constants.getattr('API_DATE_FORMAT'))}"
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

            elif max(map(lambda x: float(x["postedAtPrecise"]), posts)) >= max(
                required_ids
            ):
                pass
            elif float(timestamp or 0) >= max(required_ids):
                pass
            else:
                log.debug(f"{log_id} Required before {required_ids}")
                [required_ids.discard(float(ele["postedAtPrecise"])) for ele in posts]
                log.debug(f"{log_id} Required after {required_ids}")
                if len(required_ids) > 0:
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
            return posts, new_tasks
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    finally:
        job_progress.remove_task(task) if job_progress and task is not None else None


def trace_log_task(responseArray):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    for i in range(1, len(responseArray) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(
            i + chunk_size - 1, len(responseArray)
        )  # Adjust end_index calculation
        chunk = responseArray[i - 1 : end_index]  # Adjust slice to start at i-1
        api_str = "\n\n".join(
            map(lambda post: f"{common_logs.RAW_INNER} {post}\n\n", chunk)
        )
        log.trace(f"{common_logs.FINAL_RAW.format('Timeline')}".format(posts=api_str))
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


def trace_log_old(responseArray):
    if not is_trace():
        return
    chunk_size = constants.getattr("LARGE_TRACE_CHUNK_SIZE")
    for i in range(1, len(responseArray) + 1, chunk_size):
        # Calculate end index considering potential last chunk being smaller
        end_index = min(
            i + chunk_size - 1, len(responseArray)
        )  # Adjust end_index calculation
        chunk = responseArray[i - 1 : end_index]  # Adjust slice to start at i-1
        log.trace(
            "oldtimelines {posts}".format(
                posts="\n\n".join(list(map(lambda x: f"oldtimeline: {str(x)}", chunk)))
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


def after_log(username, after):
    log.info(
        f"""
Setting initial timeline scan date for {username} to {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))}
[yellow]Hint: append ' --after 2000' to command to force scan of all timeline posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all timeline posts + download/re-download of all files[/yellow]

            """
    )
