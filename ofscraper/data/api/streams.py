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
from ofscraper.data.api.common.check import update_check
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_streams_media,
)
from ofscraper.db.operations_.posts import (
    get_streams_post_info,
    get_youngest_streams_date,
    get_deleted_post_ids,
    mark_post_as_deleted,
)
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
from ofscraper.data.api.common.timeline import process_posts_as_individual

API = "Streams"
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
        generators = get_tasks(splitArrays, c, model_id, username, after)
        data = await process_tasks_batch(generators)
    elif len(post_id) <= of_env.getattr("MAX_STREAMS_INDIVIDUAL_SEARCH"):
        data = process_posts_as_individual()
    update_check(data, model_id, after, API)
    return data


async def get_oldstreams(model_id, username):
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
            log.traceback_(traceback.format_exc())
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
    filteredArray = list(
        filter(
            lambda x: arrow.get(x.get("created_at")).float_timestamp >= after,
            postsDataArray,
        )
    )

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]
    return splitArrays


def get_tasks(splitArrays, c, model_id, username, after):
    tasks = []

    if len(splitArrays) == 0:
        tasks.append(
            scrape_stream_posts(
                c, model_id, username, timestamp=after, is_last_chunk=True, offset=True
            )
        )
        return tasks

    first_known_post = splitArrays[0][0]
    first_known_timestamp = float(first_known_post.get("created_at"))

    if float(after) < first_known_timestamp:
        log.debug(
            f"Spawning Bridge Worker to cover gap from {after} to {first_known_timestamp}"
        )
        tasks.append(
            scrape_stream_posts(
                c,
                model_id,
                username,
                timestamp=after,
                required_posts=[
                    {
                        "post_id": first_known_post.get("post_id"),
                        "timestamp": first_known_timestamp,
                    }
                ],
                offset=True,
            )
        )

    for i, chunk in enumerate(splitArrays):
        is_first_chunk = i == 0
        is_final_chunk = i == len(splitArrays) - 1

        start_timestamp = (
            chunk[0].get("created_at")
            if is_first_chunk
            else splitArrays[i - 1][-1].get("created_at")
        )

        tasks.append(
            scrape_stream_posts(
                c,
                model_id,
                username,
                timestamp=start_timestamp,
                required_posts=[
                    {"post_id": ele.get("post_id"), "timestamp": ele.get("created_at")}
                    for ele in chunk
                ],
                is_last_chunk=is_final_chunk,
                offset=is_first_chunk or is_final_chunk,
            )
        )

    return tasks


async def scrape_stream_posts(
    c,
    model_id,
    username,
    timestamp=None,
    required_posts=None,
    is_last_chunk=False,
    offset=False,
):
    required_posts = required_posts or []
    expected_missing = [p for p in required_posts]
    required_ids = {p["post_id"] for p in required_posts}

    before = arrow.get(settings.get_settings().before or arrow.now()).float_timestamp
    start_anchor = float(timestamp) if timestamp else 0
    all_ghosts_found = []

    current_timestamp = float(timestamp) - 0.001 if timestamp and offset else timestamp
    has_more = True

    try:
        while has_more:
            url = (
                of_env.getattr("streamsNextEP").format(model_id, str(current_timestamp))
                if current_timestamp
                else of_env.getattr("streamsEP").format(model_id)
            )

            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Streams API Error: {r.status} for {url}")
                    break

                data = await r.json_()
                batch = data.get("list", [])
                has_more = data.get("hasMore", False)
                if not batch:
                    break

                batch_timestamps = [float(x.get("postedAtPrecise", 0)) for x in batch]
                max_ts = max(batch_timestamps)
                batch_ids = {x["id"] for x in batch}

                expected_missing = [
                    p for p in expected_missing if p["post_id"] not in batch_ids
                ]
                for ele in batch:
                    required_ids.discard(ele["id"])

                ghosts_in_batch = []
                for expected in expected_missing:
                    if max_ts >= expected["timestamp"] >= start_anchor:
                        ghosts_in_batch.append(expected["post_id"])

                if ghosts_in_batch:
                    all_ghosts_found.extend(ghosts_in_batch)
                    expected_missing = [
                        p
                        for p in expected_missing
                        if p["post_id"] not in ghosts_in_batch
                    ]
                    for g_id in ghosts_in_batch:
                        required_ids.discard(g_id)

                if not is_last_chunk and len(required_ids) == 0:
                    break

                if max_ts > before:
                    break

                current_timestamp = max_ts
                yield batch

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
    finally:
        if all_ghosts_found:
            log.info(
                f"Worker finished. Flagging {len(all_ghosts_found)} ghost streams in database."
            )
            await mark_post_as_deleted(
                post_ids=all_ghosts_found, model_id=model_id, username=username
            )


async def get_after(model_id, username):
    prechecks = get_after_pre_checks(model_id, API)
    if prechecks is not None:
        return max(
            arrow.get(prechecks).float_timestamp, arrow.get("2000").float_timestamp
        )

    curr = await get_streams_media(model_id=model_id, username=username)
    if len(curr) == 0:
        return arrow.get("2000").float_timestamp

    curr_downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    deleted_posts = await get_deleted_post_ids(model_id=model_id, username=username)

    filtered_items = [
        x
        for x in curr
        if x.get("downloaded") != 1
        and x.get("media_id") not in curr_downloaded
        and x.get("post_id") not in deleted_posts
        and x.get("unlocked") != 0
    ]

    if len(filtered_items) == 0:
        youngest = await get_youngest_streams_date(model_id=model_id, username=username)
        return arrow.get(youngest or "2000").float_timestamp

    unique_missing = {}
    for item in filtered_items:
        mid = item.get("media_id")
        if mid not in unique_missing or arrow.get(
            item.get("posted_at") or 0
        ) > arrow.get(unique_missing[mid].get("posted_at") or 0):
            unique_missing[mid] = item

    missing_items = sorted(
        list(unique_missing.values()), key=lambda x: arrow.get(x.get("posted_at") or 0)
    )
    return arrow.get(missing_items[0]["posted_at"] or "2000").float_timestamp


def time_log(username, after):
    log.info(
        f"Setting streams scan range for {username} from {arrow.get(after).format(of_env.getattr('API_DATE_FORMAT'))} to {arrow.get(settings.get_settings().before or arrow.now()).format((of_env.getattr('API_DATE_FORMAT')))}"
    )
