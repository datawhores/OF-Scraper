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
from ofscraper.data.api.common.timeline import process_posts_as_individual
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_timeline_media,
)
from ofscraper.db.operations_.posts import (
    get_timeline_posts_info,
    get_youngest_timeline_date,
    mark_post_as_deleted,
    get_deleted_post_ids,
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
        tasks = get_tasks(splitArrays, c, model_id, username, after)
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


def get_tasks(splitArrays, c, model_id, username, after):
    tasks = []

    # Scenario 1: Empty DB, or just hunting for brand new posts today
    if len(splitArrays) == 0:
        tasks.append(
            scrape_timeline_posts(
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
            scrape_timeline_posts(
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

    # Scenarios 2 & 3: Iterate through the known chunks dynamically
    for i, chunk in enumerate(splitArrays):
        is_first_chunk = i == 0
        is_final_chunk = i == len(splitArrays) - 1

        # Overlap logic: Start at the first element, or the last element of the previous chunk
        start_timestamp = (
            chunk[0].get("created_at")
            if is_first_chunk
            else splitArrays[i - 1][-1].get("created_at")
        )

        tasks.append(
            scrape_timeline_posts(
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


async def get_after(model_id, username):
    prechecks = get_after_pre_checks(model_id, API)
    if prechecks is not None:
        return max(
            arrow.get(prechecks).float_timestamp, arrow.get("2000").float_timestamp
        )

    curr = await get_timeline_media(model_id=model_id, username=username)
    if len(curr) == 0:
        return arrow.get("2000").float_timestamp

    curr_downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    deleted_posts = await get_deleted_post_ids(model_id=model_id, username=username)

    # 1. Filter out what we already have or know is dead
    filtered_items = [
        x
        for x in curr
        if x.get("downloaded") != 1
        and x.get("media_id") not in curr_downloaded
        and x.get("post_id") not in deleted_posts
        and x.get("unlocked") != 0
    ]

    # If nothing is missing, grab the youngest date to look for brand new posts
    if len(filtered_items) == 0:
        youngest = await get_youngest_timeline_date(
            model_id=model_id, username=username
        )
        return arrow.get(youngest or "2000").float_timestamp

    # 3. Deduplicate (Keeping newest instance for anchor)
    unique_missing = {}
    for item in filtered_items:
        mid = item.get("media_id")
        if mid not in unique_missing or arrow.get(
            item.get("posted_at") or 0
        ) > arrow.get(unique_missing[mid].get("posted_at") or 0):
            unique_missing[mid] = item

    # 4. Sort and return the oldest gap anchor
    missing_items = sorted(
        list(unique_missing.values()), key=lambda x: arrow.get(x.get("posted_at") or 0)
    )
    return arrow.get(missing_items[0]["posted_at"] or "2000").float_timestamp


async def scrape_timeline_posts(
    c,
    model_id,
    username,
    timestamp,
    required_posts=None,
    is_last_chunk=False,
    offset=False,
):
    required_posts = required_posts or []
    expected_missing = [p for p in required_posts]
    required_ids = {p["post_id"] for p in required_posts}

    # Safely get the upper limit boundary
    before = arrow.get(settings.get_settings().before or arrow.now()).float_timestamp

    # The Anchor: The earliest point this worker is responsible for
    start_anchor = float(timestamp) if timestamp else 0
    all_ghosts_found = []

    # Maintain offset calculation from old logic
    current_timestamp = float(timestamp) - 0.001 if timestamp and offset else timestamp

    ep_next = of_env.getattr("timelineNextEP")
    ep_init = of_env.getattr("timelineEP")
    url = (
        ep_next.format(model_id, current_timestamp)
        if current_timestamp
        else ep_init.format(model_id)
    )
    has_more = True

    try:
        while has_more:
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Timeline API Error: {r.status} for {url}")
                    break

                response_json = await r.json_()
                batch = response_json.get("list", [])
                has_more = response_json.get("hasMore", False)

                if not batch:
                    break

                batch_timestamps = [float(x["postedAtPrecise"]) for x in batch]
                max_ts = max(batch_timestamps)
                batch_ids = {x["id"] for x in batch}

                # 1. Clear out ANY posts we successfully found in this batch
                expected_missing = [
                    p for p in expected_missing if p["post_id"] not in batch_ids
                ]
                for ele in batch:
                    required_ids.discard(ele["id"])

                # 2. Anchored "Passed" Ghost Trap
                ghosts_in_batch = []
                for expected in expected_missing:
                    # - The API has moved PAST its expected time (max_ts >= expected)
                    # - AND the post is NEWER than our starting anchor (protects against bad starts)
                    if max_ts >= expected["timestamp"] >= start_anchor:
                        ghosts_in_batch.append(expected["post_id"])

                # 3. Process caught ghosts
                if ghosts_in_batch:
                    all_ghosts_found.extend(ghosts_in_batch)
                    expected_missing = [
                        p
                        for p in expected_missing
                        if p["post_id"] not in ghosts_in_batch
                    ]
                    for g_id in ghosts_in_batch:
                        required_ids.discard(g_id)

                # 4. Sentinel: Early Exit for Gap-Filling Chunks
                if not is_last_chunk and len(required_ids) == 0:
                    log.debug(
                        "All required gap IDs found or resolved as ghosts. Exiting early."
                    )
                    has_more = False

                # 5. Sentinel: Natural Upper Boundary Exit
                if max_ts > before:
                    log.debug("Passed the user's '--before' upper boundary. Exiting.")
                    has_more = False

                if has_more:
                    url = ep_next.format(model_id, max_ts)

                yield batch

    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())

    finally:
        # Perform the bulk DB update
        if all_ghosts_found:
            log.info(
                f"Worker finished. Flagging {len(all_ghosts_found)} deleted posts in database."
            )
            log.debug(
                f"Flagging the following post_ids as deleted for {username}: {all_ghosts_found}"
            )
            await mark_post_as_deleted(
                post_ids=all_ghosts_found, model_id=model_id, username=username
            )


def time_log(username, after):
    log.info(f"""
Setting timeline scan range for {username} from {arrow.get(after).format(of_env.getattr('API_DATE_FORMAT'))} to {arrow.get(settings.get_settings().before or arrow.now()).format((of_env.getattr('API_DATE_FORMAT')))}
[yellow]: append ' --after 2000' to command to force scan of all timeline posts + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all timeline posts + download/re-download of all files[/yellow]

            """)


def filter_timeline_post(timeline_posts):
    if settings.get_settings().timeline_strict:
        timeline_only_posts = list(filter(lambda x: x.regular_timeline, timeline_posts))
    else:
        timeline_only_posts = timeline_posts
    return timeline_only_posts
