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
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,
    get_messages_media,
)
from ofscraper.db.operations_.messages import (
    get_messages_post_info,
    get_youngest_message_date,
)
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log

API = "messages"
log = logging.getLogger("shared")


@run
async def get_messages(model_id, username, c=None, post_id=None):
    after = await get_after(model_id, username)
    post_id = post_id or []
    if len(post_id) == 0 or len(post_id) > of_env.getattr(
        "MAX_MESSAGES_INDIVIDUAL_SEARCH"
    ):
        oldmessages = await get_old_messages(model_id, username)
        before = (settings.get_settings().before).float_timestamp
        log_after_before(after, before, username)
        filteredArray = get_filterArray(after, before, oldmessages)
        splitArrays = get_split_array(filteredArray)
        tasks = get_tasks(splitArrays, filteredArray, oldmessages, model_id, c, after)
        data = await process_tasks(tasks)
    else:
        data = await process_messages_as_individual(model_id, c)

    update_check(data, model_id, after, API)
    return data


async def get_old_messages(model_id, username):
    if read_full_after_scan_check(model_id, API):
        return []
    if not settings.get_settings().api_cache_disabled:
        oldmessages = await get_messages_post_info(model_id=model_id, username=username)
    else:
        oldmessages = []
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

    # The Producer: Unwraps the generator batches into the queue
    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    # Start producers concurrently as real Tasks
    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    # The Consumer: Aggregates data as batches arrive
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

    progress_utils.api.remove_overall_task(page_task)
    log.debug(common_logs.FINAL_COUNT_POST.format("Messages", len(responseArray)))
    return responseArray


async def scrape_messages(c, model_id, message_id=None, required_ids=None):
    """
    Async Generator Worker Loop for messages.
    Yields batches immediately for memory efficiency and crash resilience.
    """
    current_message_id = message_id

    while True:
        ep = (
            of_env.getattr("messagesNextEP")
            if current_message_id
            else of_env.getattr("messagesEP")
        )
        url = ep.format(model_id, current_message_id)
        task = None

        try:
            task = progress_utils.api.add_job_task(
                f"[Messages] Message ID-> {current_message_id if current_message_id else 'initial'}",
                visible=True,
            )

            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.error(f"Messages API Error: {r.status} for {url}")
                    break

                data = await r.json_()
                if not isinstance(data, dict):
                    log.error(f"API returned unexpected format (not a dict) for {url}")
                    break

                batch = data.get("list", [])
                if not batch:
                    break
                
                # CRITICAL: Yield batch immediately
                yield batch

                trace_progress_log(f"{API} requests", batch)

                if not required_ids:
                    break

                # Prune requirements for this parallel window
                [
                    required_ids.discard(
                        arrow.get(
                            ele.get("createdAt") or ele.get("postedAt")
                        ).float_timestamp
                    )
                    for ele in batch
                ]

                # EXIT LOGIC: Window satisfied
                if len(required_ids) == 0:
                    break

                new_mid = batch[-1].get("id")
                
                # SAFETY CHECK: Prevent stuck API loop
                if str(new_mid) == str(current_message_id):
                    break
                
                # SAFETY CHECK: Boundary overshoot (timestamps decrease)
                # If the last item is older than the oldest required ID, we are done
                last_item_ts = arrow.get(batch[-1].get("createdAt") or batch[-1].get("postedAt")).float_timestamp
                if last_item_ts < min(required_ids):
                    break

                current_message_id = new_mid

        except asyncio.TimeoutError:
            log.warning(f"Task timed out {url}")
            break
        except Exception as E:
            log.error(f"Messages branch failed for {url}")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)


async def get_individual_messages_post(model_id, postid, c):
    url = of_env.getattr("messageSPECIFIC").format(model_id, postid)
    async with c.requests_async(url=url) as r:
        if not (200 <= r.status < 300):
            return {"error": True}
        data = await r.json_()
        posts = data.get("list", [])
        return posts[0] if (posts and isinstance(posts, list)) else {"error": True}


async def get_after(model_id, username):
    prechecks = get_after_pre_checks(model_id, API)
    if prechecks is not None:
        return prechecks

    curr = await get_messages_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
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

    log.info(
        f"Number of messages marked as downloaded {len(list(curr_downloaded)) - len(list(missing_items))}"
    )
    log.info(
        f"Number of messages marked as missing/undownloaded {len(list(missing_items))}"
    )

    if len(missing_items) == 0:
        log.debug(
            "Using newest db date because all downloads in db are marked as downloaded"
        )
        return arrow.get(
            await get_youngest_message_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        missing_items = sorted(
            missing_items, key=lambda x: arrow.get(x.get("posted_at") or 0)
        )
        log.debug(
            f"Setting date slightly before oldest missing item because {len(missing_items)} messages in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0]["posted_at"]).float_timestamp


def get_filterArray(after, before, oldmessages):
    oldmessages = list(filter(lambda x: x.get("created_at") is not None, oldmessages))
    oldmessages.append({"created_at": before, "post_id": None})
    oldmessages = sorted(
        oldmessages, key=lambda x: arrow.get(x["created_at"] or 0), reverse=True
    )
    if after > before:
        return []
    return oldmessages[get_i(oldmessages, before) : get_j(oldmessages, after)]


def get_i(oldmessages, before):
    """
    Finds the starting index for the slice based on the 'before' date.
    Fixed to handle sparse lists without IndexError.
    """
    if not oldmessages:
        return 0
    
    if before >= oldmessages[0].get("created_at"):
        return 0
    
    if before <= oldmessages[-1].get("created_at"):
        return max(0, len(oldmessages) - 1)

    try:
        return max(
            0,
            next(
                index - 1
                for index, m in enumerate(oldmessages)
                if (m.get("created_at") or 0) <= before
            ),
        )
    except StopIteration:
        return 0


def get_j(oldmessages, after):
    """
    Finds the ending index for the slice based on the 'after' date.
    Fixed to handle sparse lists without IndexError.
    """
    if not oldmessages:
        return 0
    
    if after >= oldmessages[0].get("created_at"):
        return 0
    
    if after <= oldmessages[-1].get("created_at"):
        return len(oldmessages)

    try:
        return min(
            len(oldmessages),
            next(
                index + 1
                for index, m in enumerate(oldmessages)
                if (m.get("created_at") or 0) <= after
            ),
        )
    except StopIteration:
        return len(oldmessages)


def get_split_array(filteredArray):
    if not filteredArray:
        return []
    min_posts = max(
        len(filteredArray) // of_env.getattr("REASONABLE_MAX_PAGE_MESSAGES"),
        of_env.getattr("MIN_PAGE_POST_COUNT"),
    )
    return [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]


def get_tasks(splitArrays, filteredArray, oldmessages, model_id, c, after):
    tasks = []
    if len(splitArrays) > 2:
        tasks.append(
            scrape_messages(
                c,
                model_id,
                message_id=splitArrays[0][0].get("post_id"),
                required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
            )
        )
        for i in range(1, len(splitArrays)):
            tasks.append(
                scrape_messages(
                    c,
                    model_id,
                    message_id=splitArrays[i - 1][-1].get("post_id"),
                    required_ids=set(
                        [ele.get("created_at") for ele in splitArrays[i]]
                    ),
                )
            )
        tasks.append(
            scrape_messages(
                c,
                model_id,
                message_id=splitArrays[-1][-1].get("post_id"),
                required_ids=set([after]),
            )
        )
    elif len(splitArrays) > 0:
        tasks.append(
            scrape_messages(
                c,
                model_id,
                required_ids=set([after]),
                message_id=(
                    splitArrays[0][0].get("post_id")
                    if len(filteredArray) != len(oldmessages)
                    else None
                ),
            )
        )
    else:
        tasks.append(
            scrape_messages(c, model_id, message_id=None, required_ids=set([after]))
        )
    return tasks


def log_after_before(after, before, username):
    log.info(
        f"Setting Message scan range for {username} from {arrow.get(after).format(of_env.getattr('API_DATE_FORMAT'))} to {arrow.get(before).format(of_env.getattr('API_DATE_FORMAT'))}"
    )