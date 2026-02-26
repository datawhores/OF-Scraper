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
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.after import get_after_pre_checks
from ofscraper.data.api.common.cache.read import read_full_after_scan_check
from ofscraper.data.api.common.check import update_check
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_streams_media,
)
from ofscraper.db.operations_.posts import (
    get_streams_post_info,
    get_youngest_streams_date,
)
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
from ofscraper.data.api.common.timeline import process_posts_as_individual

API = "streams"
log = logging.getLogger("shared")


@run
async def get_streams_posts(model_id, username, c=None, post_id=None):
    after = await get_after(model_id, username)
    time_log(username, after)
    post_id = post_id or []
    if len(post_id) == 0 or len(post_id) > of_env.getattr(
        "MAX_STREAMS_INDIVIDUAL_SEARCH"
    ):
        splitArrays = await get_split_array(model_id, username, after)
        # get_tasks now returns raw generators
        generators = get_tasks(splitArrays, c, model_id, after)
        data = await process_tasks_batch(generators)
    elif len(post_id) <= of_env.getattr("MAX_STREAMS_INDIVIDUAL_SEARCH"):
        data = process_posts_as_individual()
    update_check(data, model_id, after, API)
    return data


async def get_oldstreams(model_id, username):
    if read_full_after_scan_check(model_id, API):
        return []
    if not settings.get_settings().api_cache_disabled:
        oldstreams = await get_streams_post_info(model_id=model_id, username=username)
    else:
        oldstreams = []
    oldstreams = list(filter(lambda x: x is not None, oldstreams))
    seen = set()
    oldstreams = [
        post
        for post in oldstreams
        if post["post_id"] not in seen and not seen.add(post["post_id"])
    ]
    log.debug(f"[bold]Streams Cache[/bold] {len(oldstreams)} found")
    trace_log_raw("oldtimestreams", oldstreams)
    return oldstreams


async def process_tasks_batch(generators):
    """
    Fixed Orchestrator: Uses a Queue to consume batches from generators concurrently.
    """
    responseArray = []
    page_count = 0
    seen = set()
    queue = asyncio.Queue()

    page_task = progress_utils.api.add_overall_task(
        f"Streams Content Pages Progress: {page_count}", visible=True
    )

    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue

        page_count += 1
        progress_utils.api.update_overall_task(
            page_task,
            description=f"Streams Content Pages Progress: {page_count}",
        )

        if batch:
            new_posts = [
                post
                for post in batch
                if post.get("id") not in seen and not seen.add(post.get("id"))
            ]
            responseArray.extend(new_posts)
            trace_progress_log(f"{API} task", new_posts)

    progress_utils.api.remove_overall_task(page_task)
    log.debug(
        f"{common_logs.FINAL_IDS.format('Streams')} {list(map(lambda x: x.get('id'), responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(common_logs.FINAL_COUNT_POST.format("Streams", len(responseArray)))
    return responseArray


async def get_split_array(model_id, username, after):
    oldstreams = await get_oldstreams(model_id, username)
    if len(oldstreams) == 0:
        return []
    min_posts = max(
        len(oldstreams) // of_env.getattr("REASONABLE_MAX_PAGE"),
        of_env.getattr("MIN_PAGE_POST_COUNT"),
    )
    postsDataArray = sorted(oldstreams, key=lambda x: x.get("created_at"))
    filteredArray = list(filter(lambda x: x.get("created_at") >= after, postsDataArray))

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]
    return splitArrays


def get_tasks(splitArrays, c, model_id, after):
    """
    Returns list of raw Generators. Removed asyncio.create_task to fix TypeError.
    """
    tasks = []
    before = arrow.get(settings.get_settings().before or arrow.now()).float_timestamp
    if len(splitArrays) > 2:
        tasks.append(
            scrape_stream_posts(
                c,
                model_id,
                required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
                timestamp=splitArrays[0][0].get("created_at"),
                offset=True,
            )
        )
        for i in range(1, len(splitArrays) - 1):
            tasks.append(
                scrape_stream_posts(
                    c,
                    model_id,
                    required_ids=set([ele.get("created_at") for ele in splitArrays[i]]),
                    timestamp=splitArrays[i - 1][-1].get("created_at"),
                    offset=False,
                )
            )
        tasks.append(
            scrape_stream_posts(
                c,
                model_id,
                timestamp=splitArrays[-1][0].get("created_at"),
                offset=True,
                required_ids=set([before]),
            )
        )
    elif len(splitArrays) > 0:
        tasks.append(
            scrape_stream_posts(
                c,
                model_id,
                timestamp=splitArrays[0][0].get("created_at"),
                offset=True,
                required_ids=set([before]),
            )
        )
    else:
        tasks.append(
            scrape_stream_posts(
                c, model_id, timestamp=after, offset=True, required_ids=set([before])
            )
        )
    return tasks


async def scrape_stream_posts(
    c, model_id, timestamp=None, required_ids=None, offset=False
):
    if timestamp and (
        float(timestamp) > (settings.get_settings().before).float_timestamp
    ):
        return

    current_timestamp = float(timestamp) - 0.001 if timestamp and offset else timestamp

    while True:
        url = (
            of_env.getattr("streamsNextEP").format(model_id, str(current_timestamp))
            if current_timestamp
            else of_env.getattr("streamsEP").format(model_id)
        )

        task_label = f"[Streams] Timestamp -> {arrow.get(math.trunc(float(current_timestamp))).format(of_env.getattr('API_DATE_FORMAT')) if current_timestamp is not None else 'initial'}"
        task = progress_utils.api.add_job_task(task_label, visible=True)

        try:
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    break

                data = await r.json_()
                batch = data.get("list", [])
                if not batch:
                    break

                yield batch

                if not required_ids:
                    break

                [
                    required_ids.discard(float(ele.get("postedAtPrecise", 0)))
                    for ele in batch
                ]

                if len(required_ids) == 0:
                    break

                new_ts = batch[-1].get("postedAtPrecise")
                if str(new_ts) == str(current_timestamp) or float(new_ts) < min(
                    required_ids
                ):
                    break

                current_timestamp = new_ts

        except Exception as E:
            log.traceback_(E)
            log.traceback(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


async def get_after(model_id, username):
    prechecks = get_after_pre_checks(model_id, API)
    if prechecks is not None:
        return prechecks
    curr = await get_streams_media(model_id=model_id, username=username)
    if len(curr) == 0:
        return 0
    curr_downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    missing_items = sorted(
        [
            x
            for x in curr
            if x.get("downloaded") != 1
            and x.get("post_id") not in curr_downloaded
            and x.get("unlocked") != 0
        ],
        key=lambda x: x.get("posted_at") or 0,
    )
    if len(missing_items) == 0:
        return arrow.get(
            await get_youngest_streams_date(model_id=model_id, username=username)
        ).float_timestamp
    return arrow.get(missing_items[0]["posted_at"] or 0).float_timestamp


def time_log(username, after):
    log.info(
        f"Setting streams scan range for {username} from {arrow.get(after).format(of_env.getattr('API_DATE_FORMAT'))} to {arrow.get(settings.get_settings().before or arrow.now()).format((of_env.getattr('API_DATE_FORMAT')))}"
    )
