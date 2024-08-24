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
import  ofscraper.runner.manager as manager2
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_utils
import ofscraper.utils.settings as settings
from ofscraper.data.api.common.after import get_after_pre_checks
from ofscraper.data.api.common.cache.read import read_full_after_scan_check
from ofscraper.data.api.common.check import update_check
from ofscraper.classes.sessionmanager.sessionmanager import SessionSleep
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
sleeper = None


@run
async def get_messages(model_id, username, forced_after=None, c=None):
    global after
    after = await get_after(model_id, username, forced_after)
    if len(read_args.retriveArgs().post_id or []) == 0 or len(
        read_args.retriveArgs().post_id or []
    ) > constants.getattr("MAX_MESSAGES_INDIVIDUAL_SEARCH"):
        oldmessages = await get_old_messages(model_id, username)
        before = (read_args.retriveArgs().before).float_timestamp
        log_after_before(after, before, username)
        filteredArray = get_filterArray(after, before, oldmessages)
        splitArrays = get_split_array(filteredArray)
        # Set charged sleeper
        get_sleeper(reset=True)
        tasks = get_tasks(splitArrays, filteredArray, oldmessages, model_id, c)
        data = await process_tasks(tasks)
    elif len(read_args.retriveArgs().post_id or []) <= constants.getattr(
        "MAX_MESSAGES_INDIVIDUAL_SEARCH"
    ):
        data = process_individual(model_id)
    update_check(data, model_id, after, API)
    return data


async def get_old_messages(model_id, username):
    oldmessages = None
    if read_full_after_scan_check(model_id, API):
        return []
    if not settings.get_api_cache_disabled():
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


def process_individual(model_id):
    data = []
    for ele in read_args.retriveArgs().post_id:
        try:
            post = get_individual_messages_post(model_id, ele)
            if not post.get("error"):
                data.append(post)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    return data


async def process_tasks(tasks):
    page_count = 0
    responseArray = []
    page_task = progress_utils.add_api_task(
        f"Message Content Pages Progress: {page_count}", visible=True
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
                    description=f"Message Content Pages Progress: {page_count}",
                )
                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Messages')} {list(map(lambda x:x['id'],new_posts))}"
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
        f"{common_logs.FINAL_IDS.format('Messages')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)

    log.debug(f"{common_logs.FINAL_COUNT.format('Messages')} {len(responseArray)}")

    return responseArray


def get_filterArray(after, before, oldmessages):
    log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")
    oldmessages = list(filter(lambda x: x["created_at"] is not None, oldmessages))
    oldmessages.append({"created_at": before, "post_id": None})
    oldmessages = sorted(
        oldmessages,
        key=lambda x: arrow.get(x["created_at"] or 0),
        reverse=True,
    )
    if after > before:
        return []
    elif len(oldmessages) <= 2:
        return oldmessages
    else:
        return oldmessages[get_i(oldmessages, before) : get_j(oldmessages, after)]


def get_i(oldmessages, before):
    """
    iterate through posts until a date less then or equal
    to before , set index to -1 thtemp))nt
    """
    if before >= oldmessages[1].get("created_at"):
        return 0
    if before <= oldmessages[-1].get("created_at"):
        return len(oldmessages) - 2
    # Use a generator expression for efficiency
    return max(
        next(
            index - 1
            for index, message in enumerate(oldmessages)
            if message.get("created_at") <= before
        ),
        0,
    )


def get_j(oldmessages, after):
    """
    iterate through posts until a date less then or equal
    to after , set index to +1 this point
    """
    if after >= oldmessages[0].get("created_at"):
        return 0
    if after <= oldmessages[-1].get("created_at"):
        return len(oldmessages)
    return min(
        next(
            index + 1
            for index, message in enumerate(oldmessages)
            if message.get("created_at") <= after
        ),
        len(oldmessages) - 1,
    )


def get_split_array(filteredArray):
    min_posts = max(
        len(filteredArray) // constants.getattr("REASONABLE_MAX_PAGE_MESSAGES"),
        constants.getattr("MIN_PAGE_POST_COUNT"),
    )

    return [
        filteredArray[i : i + min_posts]
        for i in range(0, len(filteredArray), min_posts)
    ]


def get_tasks(splitArrays, filteredArray, oldmessages, model_id, c):
    tasks = []
    # special case pass after to stop work
    if len(splitArrays) > 2:
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    message_id=(splitArrays[0][0].get("post_id")),
                    required_ids=set([ele.get("created_at") for ele in splitArrays[0]]),
                )
            )
        )
        [
            tasks.append(
                asyncio.create_task(
                    scrape_messages(
                        c,
                        model_id,
                        message_id=splitArrays[i - 1][-1].get("post_id"),
                        required_ids=set(
                            [ele.get("created_at") for ele in splitArrays[i]]
                        ),
                    )
                )
            )
            for i in range(1, len(splitArrays))
        ]
        # keeping grabbing until nothing left
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    message_id=splitArrays[-1][-1].get("post_id"),
                    required_ids=set([after]),
                )
            )
        )
    # use the first split if less then 3
    elif len(splitArrays) > 0:
        tasks.append(
            asyncio.create_task(
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
        )
    # set init message to none
    else:
        tasks.append(
            asyncio.create_task(
                scrape_messages(
                    c,
                    model_id,
                    message_id=None,
                    required_ids=set([after]),
                )
            )
        )
    return tasks


async def scrape_messages(c, model_id, message_id=None, required_ids=None) -> list:
    messages = None
    ep = (
        constants.getattr("messagesNextEP")
        if message_id
        else constants.getattr("messagesEP")
    )
    url = ep.format(model_id, message_id)
    log.debug(f"{message_id if message_id else 'init'} {url}")
    log_id = f"offset messageid:{message_id if message_id else 'init messageid'}"
    new_tasks = []
    task = None
    log.debug(
        f"trying access {API.lower()} posts with url:{url} message_id:{message_id}"
    )

    try:
        async with c.requests_async(url=url, sleeper=get_sleeper()) as r:
            task = progress_utils.add_api_job_task(
                f"[Messages] Message ID-> {message_id if message_id else 'initial'}"
            )
            log.debug(
                f"successfully accessed {API.lower()} posts with url:{url} message_id:{message_id}"
            )
            messages = (await r.json_())["list"]

            if not bool(messages):
                log.debug(f"{log_id} -> no messages found")
                return [], []
            log.debug(f"{log_id} -> number of messages found {len(messages)}")
            log.debug(
                f"{log_id} -> first date {arrow.get(messages[0].get('createdAt') or messages[0].get('postedAt')).format(constants.getattr('API_DATE_FORMAT'))}"
            )
            log.debug(
                f"{log_id} -> last date {arrow.get(messages[-1].get('createdAt') or messages[0].get('postedAt')).format(constants.getattr('API_DATE_FORMAT'))}"
            )
            log.debug(
                f"{log_id} -> found message ids {list(map(lambda x:x.get('id'),messages))}"
            )
            trace_progress_log(f"{API} requests", messages)

            # check if first value(newest) is less then then the required time
            if max(
                map(
                    lambda x: arrow.get(
                        x.get("createdAt", 0) or x.get("postedAt", 0)
                    ).float_timestamp,
                    messages,
                )
            ) <= min(required_ids):
                pass
            else:
                [
                    required_ids.discard(
                        arrow.get(
                            ele.get("createdAt") or ele.get("postedAt")
                        ).float_timestamp
                    )
                    for ele in messages
                ]

                if len(required_ids) > 0:
                    new_tasks.append(
                        asyncio.create_task(
                            scrape_messages(
                                c,
                                model_id,
                                message_id=messages[-1]["id"],
                                required_ids=required_ids,
                            )
                        )
                    )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")
    except Exception as E:

        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    finally:
        progress_utils.remove_api_job_task(task)
    return messages, new_tasks


def get_individual_messages_post(model_id, postid):
    with manager2.Manager.get_ofsession(
        backend="httpx",
    ) as c:
        with c.requests(
            url=constants.getattr("messageSPECIFIC").format(model_id, postid)
        ) as r:
            log.trace(f"message raw individual {r.json()}")
            return r.json()["list"][0]


async def get_after(model_id, username, forced_after=None):
    prechecks = get_after_pre_checks(model_id, API, forced_after=forced_after)
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
    missing_items = list(
        filter(lambda x: x.get("downloaded") != 1 and x.get("unlocked") != 0, curr)
    )
    missing_items = list(
        sorted(missing_items, key=lambda x: arrow.get(x.get("posted_at") or 0))
    )
    log.info(
        f"Number of messages marked as downloaded {len(list(curr_downloaded))-len(list(missing_items))}"
    )
    log.info(
        f"Number of messages marked as missing/undownloaded {len(list(missing_items))}"
    )
    if len(list(missing_items)) == 0:
        log.debug(
            "Using newest db date because,all downloads in db are marked as downloaded"
        )
        return arrow.get(
            await get_youngest_message_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        log.debug(
            f"Setting date slightly before oldest missing item\nbecause {len(missing_items)} messages in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0]["posted_at"]).float_timestamp


def log_after_before(after, before, username):

    log.info(
        f"""
Setting Message scan range for {username} from {arrow.get(after).format(constants.getattr('API_DATE_FORMAT'))} to {arrow.get(before).format(constants.getattr('API_DATE_FORMAT'))}

[yellow]Hint: append ' --after 2000' to command to force scan of all messages + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --force-all' to command to force scan of all messages + download/re-download of all files[/yellow]

        """
    )


def get_sleeper(reset=False):
    global sleeper
    if not sleeper:
        sleeper = SessionSleep(sleep=None)
    if reset:
        sleeper.reset_sleep()
    return sleeper
