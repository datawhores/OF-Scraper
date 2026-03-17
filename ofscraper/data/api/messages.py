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
    get_messages_media,
)
from ofscraper.db.operations_.messages import (
    get_messages_post_info,
    get_newest_message_date,
    mark_message_as_deleted,
    get_deleted_messages_ids,
)
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
import ofscraper.utils.const as const


API = "Messages"
log = logging.getLogger("shared")


@run
async def get_messages(model_id, username, c=None, post_id=None):
    after = await get_after(model_id, username)

    time_log(username, after)
    post_id = post_id or []

    if len(post_id) == 0 or len(post_id) > of_env.getattr(
        "MAX_MESSAGES_INDIVIDUAL_SEARCH"
    ):
        splitArrays, anchor_id = await get_split_array(model_id, username, after)
        generators = get_tasks(splitArrays, anchor_id, c, model_id, username, after)
        data = await process_tasks(generators)
    else:
        data = await process_messages_as_individual(model_id, c)

    update_check(data, model_id, after, API)
    return data


async def get_old_messages(model_id, username):
    if not settings.get_settings().api_cache_disabled:
        oldmessages = await get_messages_post_info(model_id=model_id, username=username)
    else:
        oldmessages = []

    oldmessages = list(filter(lambda x: x is not None, oldmessages))
    seen = set()
    oldmessages = [
        post
        for post in oldmessages
        if post["post_id"] not in seen and not seen.add(post["post_id"])
    ]
    log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")
    trace_log_raw("oldmessages", oldmessages)
    return oldmessages


async def process_messages_as_individual(model_id, c):
    data = []
    if not c:
        return data
    for ele in settings.get_settings().post_id or []:
        try:
            post = await get_individual_messages_post(model_id, ele, c)
            if post and not post.get("error"):
                data.append(post)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    return data


async def process_tasks(generators):
    page_count = 0
    responseArray = []
    page_task = progress_utils.api.add_overall_task(
        f"Message Content Pages Progress: {page_count}", visible=True
    )
    seen = set()
    queue = asyncio.Queue()

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
            description=f"Message Content Pages Progress: {page_count}",
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
        f"{common_logs.FINAL_IDS.format('Messages')} {list(map(lambda x: x.get('id'), responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(common_logs.FINAL_COUNT_POST.format("Messages", len(responseArray)))
    return responseArray


async def get_split_array(model_id, username, after):
    oldmessages = await get_old_messages(model_id, username)
    if len(oldmessages) == 0:
        return [], None

    before = arrow.get(settings.get_settings().before or arrow.now()).float_timestamp

    # Sort descending (Newest first)
    postsDataArray = sorted(
        oldmessages,
        key=lambda x: arrow.get(x.get("created_at") or 0).float_timestamp,
        reverse=True,
    )

    # Read the cache from Oldest to Newest. Find the first message that is NEWER than our 'before' limit.
    # This guarantees the API sweeps perfectly over the 'before' boundary without missing a gap.
    anchor_id = next(
        (
            m.get("post_id")
            for m in reversed(postsDataArray)
            if float(m.get("created_at") or 0) >= before
        ),
        None,
    )

    # Filter out anything older than 'after' OR newer than 'before'
    filteredArray = [
        x for x in postsDataArray if after <= float(x.get("created_at") or 0) <= before
    ]

    min_posts = max(
        len(oldmessages) // of_env.getattr("REASONABLE_MAX_PAGE_MESSAGES"),
        of_env.getattr("MIN_PAGE_POST_COUNT"),
    )

    splitArrays = [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]

    return splitArrays, anchor_id


def get_tasks(splitArrays, anchor_id, c, model_id, username, after):
    tasks = []

    # Scenario 1: Empty DB, or just hunting for brand new messages
    if len(splitArrays) == 0:
        tasks.append(
            scrape_messages(
                c,
                model_id,
                username,
                message_id=anchor_id,
                is_last_chunk=True,
                after=after,
            )
        )
        return tasks

    # Scenarios 2 & 3: Dynamic Chunking
    for i, chunk in enumerate(splitArrays):
        is_first_chunk = i == 0
        is_final_chunk = i == len(splitArrays) - 1

        # The first chunk uses the teleport anchor.
        # Subsequent chunks use the ID of the OLDEST message in the previous chunk.
        start_id = (
            anchor_id if is_first_chunk else splitArrays[i - 1][-1].get("post_id")
        )
        start_timestamp = (
            arrow.now().float_timestamp
            if is_first_chunk
            else float(splitArrays[i - 1][-1].get("created_at"))
        )

        tasks.append(
            scrape_messages(
                c,
                model_id,
                username,
                message_id=start_id,
                start_timestamp=start_timestamp,
                required_posts=[
                    {"post_id": ele.get("post_id"), "timestamp": ele.get("created_at")}
                    for ele in chunk
                ],
                is_last_chunk=is_final_chunk,
                after=after,
            )
        )

    return tasks


async def scrape_messages(
    c,
    model_id,
    username,
    message_id=None,
    start_timestamp=None,
    required_posts=None,
    is_last_chunk=False,
    after=0,
):
    required_posts = required_posts or []
    expected_missing = [p for p in required_posts]
    required_ids = {p["post_id"] for p in required_posts}

    # Anchor point for the Inverted Ghost Trap
    start_anchor = start_timestamp if start_timestamp else arrow.now().float_timestamp
    all_ghosts_found = []

    current_message_id = message_id
    has_more = True

    try:
        while has_more:
            ep = (
                of_env.getattr("messagesNextEP")
                if current_message_id
                else of_env.getattr("messagesEP")
            )
            url = ep.format(model_id, current_message_id)

            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Messages API Error: {r.status} for {url}")
                    break

                data = await r.json_()
                if not isinstance(data, dict):
                    log.debug(f"API returned unexpected format (not a dict) for {url}")
                    break

                batch = data.get("list", [])
                has_more = data.get("hasMore", False)
                if not batch:
                    break

                # Extract timestamps and IDs
                batch_timestamps = [
                    float(
                        arrow.get(
                            x.get("createdAt") or x.get("postedAt")
                        ).float_timestamp
                    )
                    for x in batch
                ]
                min_ts = min(batch_timestamps)  # The oldest message in this batch
                batch_ids = {x["id"] for x in batch}

                # Clear found IDs
                expected_missing = [
                    p for p in expected_missing if p["post_id"] not in batch_ids
                ]
                for ele in batch:
                    required_ids.discard(ele["id"])

                # THE INVERTED GHOST TRAP:
                # If the API returns messages that are historically OLDER than an expected message,
                # we know the API skipped right over it.
                ghosts_in_batch = []
                for expected in expected_missing:
                    if min_ts <= expected["timestamp"] <= start_anchor:
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

                # Boundary condition: We hit our "after" date limit
                if min_ts < after:
                    break

                # Prevent stuck loop
                new_mid = batch[-1].get("id")
                if str(new_mid) == str(current_message_id):
                    break

                current_message_id = new_mid
                yield batch

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
    finally:
        if all_ghosts_found:
            log.info(
                f"Worker finished. Flagging {len(all_ghosts_found)} ghost messages in database."
            )
            await mark_message_as_deleted(
                post_ids=all_ghosts_found, model_id=model_id, username=username
            )


async def get_individual_messages_post(model_id, postid, c):
    url = of_env.getattr("messageSPECIFIC").format(model_id, postid)
    async with c.requests_async(url=url) as r:
        if not (200 <= r.status < 300):
            log.debug(f"Individual Messages API Error: {r.status} for {url}")
            return {"error": True}
        data = await r.json_()
        posts = data.get("list", [])
        return posts[0] if (posts and isinstance(posts, list)) else {"error": True}


async def get_after(model_id, username):

    prechecks = get_after_pre_checks(model_id, API)
    if prechecks is not None:
        return max(float(prechecks), arrow.get("2000").float_timestamp)

    curr = await get_messages_media(model_id=model_id, username=username)
    if len(curr) == 0:
        return arrow.get("2000").float_timestamp

    curr_downloaded = await get_media_ids_downloaded_model(
        model_id=model_id, username=username
    )
    deleted_messages = await get_deleted_messages_ids(
        model_id=model_id, username=username
    )

    active_media = settings.get_settings().mediatypes or ["Videos", "Audios", "Images"]
    active_media_mapped = {const.MEDIA_ALIASES.get(m.lower(), m.lower()) for m in active_media}

    filtered_items = [
        x
        for x in curr
        if x.get("downloaded") != 1
        and x.get("media_id") not in curr_downloaded
        and x.get("post_id") not in deleted_messages
        and x.get("unlocked") != 0
        and const.MEDIA_ALIASES.get(str(x.get("media_type", "")).lower(), str(x.get("media_type", "")).lower()) in active_media_mapped
    ]

    if len(filtered_items) == 0:
        newest = await get_newest_message_date(model_id=model_id, username=username)
        return max(float(newest or 0), arrow.get("2000").float_timestamp)

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
    return max(
        float(missing_items[0]["posted_at"] or 0), arrow.get("2000").float_timestamp
    )

def time_log(username, after):
    log.info(
        f"Setting Message scan range for {username} from {arrow.get(after).format(of_env.getattr('API_DATE_FORMAT'))} to {arrow.get(settings.get_settings().before or arrow.now()).format((of_env.getattr('API_DATE_FORMAT')))}"
    )
