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
import math
import traceback

import arrow

import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.after import get_after_pre_checks
from ofscraper.data.api.common.cache.read import read_full_after_scan_check
from ofscraper.data.api.common.check import update_check
from ofscraper.data.api.common.timeline import process_individual
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_timeline_media,
)
from ofscraper.db.operations_.posts import (
    get_timeline_posts_info,
    get_youngest_timeline_date,
)
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log


log = logging.getLogger("shared")
API = "timeline"


@run
async def get_timeline_posts(model_id, username, forced_after=None, c=None):

    after = await get_after(model_id, username, forced_after)
    time_log(username, after)
    if len(read_args.retriveArgs().post_id or []) == 0 or len(
        read_args.retriveArgs().post_id or []
    ) > constants.getattr("MAX_TIMELINE_INDIVIDUAL_SEARCH"):
        splitArrays = await get_split_array(model_id, username, after)
        tasks = get_tasks(splitArrays, c, model_id, after)
        data = await process_tasks_batch(tasks)
    elif len(read_args.retriveArgs().post_id or []) <= constants.getattr(
        "MAX_TIMELINE_INDIVIDUAL_SEARCH"
    ):
        data = process_individual()

    update_check(data, model_id, after, API)
    return data


async def process_tasks_batch(tasks):
    responseArray = []
    page_count = 0

    page_task = progress_utils.add_api_task(
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
                progress_utils.update_api_task(
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
                trace_progress_log(f"{API} tasks", new_posts)
                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks

    progress_utils.remove_api_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Timeline')} {list(map(lambda x:x['id'],responseArray))}"
    )
    log.debug(f"{common_logs.FINAL_COUNT.format('Timeline')} {len(responseArray)}")
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    return responseArray


async def get_oldtimeline(model_id, username):
    if read_full_after_scan_check(model_id, API):
        return []
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
    trace_log_raw("oldtimeline", oldtimeline)
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
    # special case pass before to stop work
    before = arrow.get(read_args.retriveArgs().before or arrow.now()).float_timestamp

    if len(splitArrays) > 2:
        tasks.append(
            asyncio.create_task(
                scrape_timeline_posts(
                    c,
                    model_id,
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
                    timestamp=splitArrays[-1][0].get("created_at"),
                    offset=True,
                    required_ids=set([before]),
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
                    timestamp=splitArrays[0][0].get("created_at"),
                    offset=True,
                    required_ids=set([before]),
                )
            )
        )
    # use after if split is empty i.e no db data
    else:
        tasks.append(
            asyncio.create_task(
                scrape_timeline_posts(
                    c,
                    model_id,
                    timestamp=after,
                    offset=True,
                    required_ids=set([before]),
                )
            )
        )

    return tasks


async def get_after(model_id, username, forced_after=None):
    prechecks = get_after_pre_checks(model_id, API, forced_after=forced_after)
    if prechecks is not None:
        return prechecks
    curr = await get_timeline_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting oldest date to zero because database is empty")
        return 0
    curr_downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )

    missing_items = list(
        filter(
            lambda x: x.get("downloaded") != 1
            and x.get("post_id") not in curr_downloaded
            and x.get("unlocked") != 0,
            curr,
        )
    )

    missing_items = list(sorted(missing_items, key=lambda x: arrow.get(x["posted_at"])))
    log.info(
        f"Number of timeline posts marked as downloaded {len(list(curr_downloaded))-len(list(missing_items))}"
    )
    log.info(
        f"Number of timeline posts  marked as missing/undownloaded {len(list(missing_items))}"
    )

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
    c, model_id, timestamp=None, required_ids=None, offset=False
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
    task = None

    try:
        task = progress_utils.add_api_job_task(
            f"[Timeline] Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}",
            visible=True,
        )
        log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"

        log.debug(
            f"trying access {API.lower()} posts with url:{url} timestamp:{timestamp if timestamp is not None else 'initial'}"
        )

        async with c.requests_async(url=url) as r:
            posts = (await r.json_())["list"]
            log.debug(
                f"successfully accessed {API.lower()} posts with url:{url} timestamp:{timestamp if timestamp is not None else 'initial'}"
            )

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
            trace_progress_log(f"{API} requests", posts, offset=offset)
            if min(map(lambda x: float(x["postedAtPrecise"]), posts)) >= max(
                required_ids
            ):
                pass
            elif float(timestamp or 0) >= max(required_ids):
                pass
            else:
                log.debug(f"{log_id} Required before change: {required_ids}")
                [required_ids.discard(float(ele["postedAtPrecise"])) for ele in posts]
                log.debug(f"{log_id} Required after change: {required_ids}")
                if len(required_ids) > 0:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_timeline_posts(
                                c,
                                model_id,
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
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    finally:
        progress_utils.remove_api_job_task(task)


def time_log(username, after):
    log.info(
        f"""
Setting timeline scan range for {username} from {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))} to {arrow.get(read_args.retriveArgs().before or arrow.now()).format((constants.getattr('API_DATE_FORMAT')))}
[yellow]Hint: append ' --after 2000' to command to force scan of all timeline posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all timeline posts + download/re-download of all files[/yellow]

            """
    )
