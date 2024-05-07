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
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import get_archived_media
from ofscraper.db.operations_.posts import (
    get_archived_post_info,
    get_youngest_archived_date,
)
from ofscraper.utils.context.run_async import run
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")


sem = None


@run
async def get_archived_posts_progress(model_id, username, forced_after=None, c=None):

    oldarchived = None
    if not settings.get_api_cache_disabled():
        oldarchived = await get_archived_post_info(model_id=model_id, username=username)
    else:
        oldarchived = []
    trace_log_old(oldarchived)

    log.debug(f"[bold]Archived Cache[/bold] {len(oldarchived)} found")
    oldarchived = list(filter(lambda x: x is not None, oldarchived))
    after = await get_after(model_id, username, forced_after)
    after_log(username, after)
    splitArrays = get_split_array(oldarchived, after)
    tasks = get_tasks(splitArrays, c, model_id, after)
    data = await process_tasks(tasks, model_id, after)
    progress_utils.archived_layout.visible = False
    return data


@run
async def get_archived_posts(model_id, username, forced_after=None, c=None):
    if not settings.get_api_cache_disabled():
        oldarchived = await get_archived_post_info(model_id=model_id, username=username)
    else:
        oldarchived = []
    trace_log_old(oldarchived)

    log.debug(f"[bold]Archived Cache[/bold] {len(oldarchived)} found")
    oldarchived = list(filter(lambda x: x is not None, oldarchived))
    after = await get_after(model_id, username, forced_after)
    after_log(username, after)
    with progress_utils.set_up_api_archived():
        splitArrays = get_split_array(oldarchived, after)
        tasks = get_tasks(splitArrays, c, model_id, after)
        return await process_tasks(tasks, model_id, after)


async def process_tasks(tasks, model_id, after):
    responseArray = []
    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
        f"Archived Content Pages Progress: {page_count}", visible=True
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
                    description=f"Archived Content Pages Progress: {page_count}",
                )

                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Archived')} {list(map(lambda x:x['id'],new_posts))}"
                )
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Archived')}".format(
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

    overall_progress.remove_task(page_task)

    log.debug(
        f"{common_logs.FINAL_IDS.format('Archived')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_task(responseArray)
    log.debug(f"{common_logs.FINAL_COUNT.format('Archived')} {len(responseArray)}")

    set_check(responseArray, model_id, after)
    return responseArray


def get_split_array(oldarchived, after):
    if len(oldarchived) == 0:
        return []
    min_posts = max(
        len(oldarchived) // constants.getattr("REASONABLE_MAX_PAGE"),
        constants.getattr("MIN_PAGE_POST_COUNT"),
    )
    log.debug(f"[bold]Archived Cache[/bold] {len(oldarchived)} found")
    oldarchived = list(filter(lambda x: x is not None, oldarchived))
    postsDataArray = sorted(oldarchived, key=lambda x: x.get("created_at"))
    filteredArray = list(filter(lambda x: x.get("created_at") >= after, postsDataArray))

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]
    return splitArrays


def get_tasks(splitArrays, c, model_id, after):
    tasks = []
    job_progress = progress_utils.archived_progress
    if len(splitArrays) > 2:
        tasks.append(
            asyncio.create_task(
                scrape_archived_posts(
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
                    scrape_archived_posts(
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
                scrape_archived_posts(
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
                scrape_archived_posts(
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
                scrape_archived_posts(
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
            for post in cache.get(f"archived_check_{model_id}", default=[]) + unduped
            if post["id"] not in seen and not seen.add(post["id"])
        ]

        cache.set(
            f"archived_check_{model_id}",
            all_posts,
            expire=constants.getattr("THREE_DAY_SECONDS"),
        )
        cache.close()


async def get_after(model_id, username, forced_after=None):
    if forced_after is not None:
        return forced_after
    elif not settings.get_after_enabled():
        return 0
    elif read_args.retriveArgs().after == 0:
        return 0
    elif read_args.retriveArgs().after:
        return read_args.retriveArgs().after.float_timestamp

    elif cache.get(f"{model_id}_full_archived_scrape"):
        log.info(
            "Used --after previously. Scraping all archived posts required to make sure content is not missing"
        )
        return 0
    curr = await get_archived_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
        return 0
    missing_items = list(filter(lambda x: x.get("downloaded") != 1, curr))
    missing_items = list(sorted(missing_items, key=lambda x: x.get("posted_at") or 0))
    if len(missing_items) == 0:
        log.debug(
            "Using newest db date because,all downloads in db marked as downloaded"
        )
        return arrow.get(
            await get_youngest_archived_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        log.debug(
            f"Setting date slightly before earliest missing item\nbecause {len(missing_items)} posts in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0]["posted_at"] or 0).float_timestamp


async def scrape_archived_posts(
    c, model_id, job_progress=None, timestamp=None, required_ids=None, offset=False
) -> list:
    global sem
    posts = None
    if timestamp and (
        float(timestamp)
        > (read_args.retriveArgs().before or arrow.now()).float_timestamp
    ):
        return []
    timestamp = float(timestamp) - 1000 if timestamp and offset else timestamp
    url = (
        constants.getattr("archivedNextEP").format(model_id, str(timestamp))
        if timestamp
        else constants.getattr("archivedEP").format(model_id)
    )
    log.debug(url)
    new_tasks = []
    try:
        task = (
            job_progress.add_task(
                f"Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url) as r:
            posts = (await r.json_())["list"]
            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"
            if not bool(posts):
                log.debug(f"{log_id} -> no posts found")
                return [], []
            log.debug(f"{log_id} -> number of archived post found {len(posts)}")
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
                        map(
                            lambda x: f"scrapeinfo archive: {str(x)}",
                            posts,
                        )
                    ),
                )
            )

            if not required_ids:
                new_tasks.append(
                    asyncio.create_task(
                        scrape_archived_posts(
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
                            scrape_archived_posts(
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
    except asyncio.TimeoutError as _:
        raise Exception(f"Task timed out {url}")
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task) if job_progress and task else None
    return posts, new_tasks


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
        log.trace(f"{common_logs.FINAL_RAW.format('Archived')}".format(posts=api_str))
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
            "oldarchived {posts}".format(
                posts="\n\n".join(list(map(lambda x: f"oldarchived: {str(x)}", chunk)))
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


def after_log(username, after):
    log.info(
        f"""
Setting initial archived scan date for {username} to {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))}
[yellow]Hint: append ' --after 2000' to command to force scan of all archived posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all archived posts + download/re-download of all files[/yellow]

            """
    )
