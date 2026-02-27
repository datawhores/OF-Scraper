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

import arrow

import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.after import get_after_pre_checks
from ofscraper.data.api.common.cache.read import read_full_after_scan_check
from ofscraper.data.api.common.check import update_check
from ofscraper.data.api.common.timeline import process_posts_as_individual
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
API = "Timeline"


@run
async def get_timeline_posts(model_id, username, c=None, post_id=None):

    after = await get_after(model_id, username)
    post_id = post_id or []
    time_log(username, after)
    if len(post_id) == 0 or len(post_id) > of_env.getattr(
        "MAX_TIMELINE_INDIVIDUAL_SEARCH"
    ):
        splitArrays = await get_split_array(model_id, username, after)
        tasks = get_tasks(splitArrays, c, model_id, after)
        data = await process_tasks(tasks)
    elif len(post_id) <= of_env.getattr("MAX_TIMELINE_INDIVIDUAL_SEARCH"):
        data = process_posts_as_individual()

    update_check(data, model_id, after, API)
    return data


async def process_tasks(generators):
    """
    Consumes async generators using a shared Queue.
    This replaces the old list-based batch processing.
    """
    responseArray = []
    page_count = 0
    seen = set()
    queue = asyncio.Queue()

    page_task = progress_utils.api.add_overall_task(
        f"Timeline Content Pages Progress: {page_count}", visible=True
    )

    # Internal worker to 'produce' data from generators into the queue
    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)  # Signal completion for this specific generator

    # Schedule producers as concurrent tasks
    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    # Consume batches as they arrive in the queue
    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue

        page_count += 1
        progress_utils.api.update_overall_task(
            page_task,
            description=f"Timeline Content Pages Progress: {page_count}",
        )

        if batch:
            new_posts = [
                post
                for post in batch
                if post.get("id") not in seen and not seen.add(post.get("id"))
            ]
            log.debug(
                f"{common_logs.PROGRESS_IDS.format('Timeline')} {list(map(lambda x:x['id'],new_posts))}"
            )
            trace_progress_log(f"{API} task", new_posts)
            responseArray.extend(new_posts)

    progress_utils.api.remove_overall_task(page_task)
    return responseArray


async def get_oldtimeline(model_id, username):
    if read_full_after_scan_check(model_id, API):
        return []
    if not settings.get_settings().api_cache_disabled:
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
        len(oldtimeline) // of_env.getattr("REASONABLE_MAX_PAGE"),
        of_env.getattr("MIN_PAGE_POST_COUNT"),
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
    before = arrow.get(settings.get_settings().before or arrow.now()).float_timestamp

    if len(splitArrays) > 2:
        tasks.append(
            scrape_timeline_posts(
                c,
                model_id,
                required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
                timestamp=splitArrays[0][0].get("created_at"),
                offset=True,
            )
        )
        for i in range(1, len(splitArrays) - 1):
            tasks.append(
                scrape_timeline_posts(
                    c,
                    model_id,
                    required_ids=set([ele.get("created_at") for ele in splitArrays[i]]),
                    timestamp=splitArrays[i - 1][-1].get("created_at"),
                    offset=False,
                )
            )
        tasks.append(
            scrape_timeline_posts(
                c,
                model_id,
                timestamp=splitArrays[-1][0].get("created_at"),
                offset=True,
                required_ids=set([before]),
            )
        )
    elif len(splitArrays) > 0:
        tasks.append(
            scrape_timeline_posts(
                c,
                model_id,
                timestamp=splitArrays[0][0].get("created_at"),
                offset=True,
                required_ids=set([before]),
            )
        )
    else:
        tasks.append(
            scrape_timeline_posts(
                c,
                model_id,
                timestamp=after,
                offset=True,
                required_ids=set([before]),
            )
        )
    return tasks


async def get_after(model_id, username):
    prechecks = get_after_pre_checks(model_id, API)
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
):

    current_timestamp = float(timestamp) - 0.001 if timestamp and offset else timestamp

    while True:
        url = (
            of_env.getattr("timelineNextEP").format(model_id, str(current_timestamp))
            if current_timestamp
            else of_env.getattr("timelineEP").format(model_id)
        )

        try:
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.error(f"API Error: {r.status}")
                    break  # Stop this block, but previously yielded data is safe

                data = await r.json_()
                batch = data.get("list", [])

                if not batch:
                    break

                yield batch

                if not required_ids:
                    break

                # Prune requirements
                [required_ids.discard(float(ele["postedAtPrecise"])) for ele in batch]

                if len(required_ids) == 0:
                    break

                new_ts = batch[-1]["postedAtPrecise"]

                if str(new_ts) == str(current_timestamp) or float(new_ts) < min(
                    required_ids
                ):
                    break

                current_timestamp = new_ts

        except Exception as E:
            log.error(f"Error in timeline worker at {current_timestamp}")
            log.traceback_(E)
            log.traceback(traceback.format_exc())
            break


def time_log(username, after):
    log.info(
        f"""
Setting timeline scan range for {username} from {arrow.get(after).format(of_env.getattr('API_DATE_FORMAT'))} to {arrow.get(settings.get_settings().before or arrow.now()).format((of_env.getattr('API_DATE_FORMAT')))}
[yellow]Hint: append ' --after 2000' to command to force scan of all timeline posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all timeline posts + download/re-download of all files[/yellow]

            """
    )


def filter_timeline_post(timeline_posts):
    if settings.get_settings().timeline_strict:
        timeline_only_posts = list(filter(lambda x: x.regular_timeline, timeline_posts))
    else:
        timeline_only_posts = timeline_posts
    return timeline_only_posts
