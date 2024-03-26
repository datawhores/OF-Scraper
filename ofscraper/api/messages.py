r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor

import arrow
from diskcache import Cache
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_random

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.constants as constants
import ofscraper.db.operations as operations
import ofscraper.utils.args as args_
import ofscraper.utils.config as config_
import ofscraper.utils.console as console
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.run_async import run

from ..utils.paths import getcachepath

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")

sem = semaphoreDelayed(constants.MAX_SEMAPHORE)


@run
async def get_messages(model_id, username, forced_after=None, rescan=None):
    with ThreadPoolExecutor(max_workers=20) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(
                style=Style(color="blue"),
            ),
            TextColumn("Getting Messages...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))
        global tasks
        global after
        global new_tasks

        new_tasks = []
        tasks = []
        responseArray = []
        page_count = 0
        # require a min num of posts to be returned
        min_posts = 40
        with Live(
            progress_group,
            refresh_per_second=constants.refreshScreen,
            console=console.get_shared_console(),
        ):
            async with sessionbuilder.sessionBuilder() as c:
                if not args_.getargs().no_cache:
                    oldmessages = operations.get_messages_data(
                        model_id=model_id, username=username
                    )
                else:
                    oldmessages = []
                log.trace(
                    "oldmessage {posts}".format(
                        posts="\n\n".join(
                            list(map(lambda x: f"oldmessages: {str(x)}", oldmessages))
                        )
                    )
                )
                oldmessages = list(
                    filter(lambda x: (x.get("date")) != None, oldmessages)
                )
                log.debug(f"[bold]Messages Cache[/bold] {len(oldmessages)} found")

                oldmessages = sorted(
                    oldmessages,
                    key=lambda x: arrow.get(x.get("date")).float_timestamp,
                    reverse=True,
                )
                oldmessages = [
                    {"date": arrow.now().float_timestamp, "id": None}
                ] + oldmessages

                before = (args_.getargs().before or arrow.now()).float_timestamp
                after = after = (
                    0 if rescan else forced_after or get_after(model_id, username)
                )
                log.debug(f"Messages after = {after}")

                log.debug(f"Messages before = {before}")

                if after > before:
                    return []
                if len(oldmessages) <= 2:
                    filteredArray = oldmessages
                else:
                    i = None
                    j = None

                    if before >= oldmessages[1].get("date"):
                        i = 0
                    elif before <= oldmessages[-1].get("date"):
                        i = len(oldmessages) - 2
                    else:
                        i = (
                            list(x.get("date") > before for x in oldmessages).index(
                                False
                            )
                            - 1
                        )

                    if after >= oldmessages[1].get("date"):
                        j = 2
                    elif after < oldmessages[-1].get("date"):
                        j = len(oldmessages)
                    else:
                        temp = list(x.get("date") < after for x in oldmessages)
                        j = temp.index(True) if True in temp else len(oldmessages)
                    j = min(max(i + 2, j), len(oldmessages))
                    i = max(min(j - 2, i), 0)
                    log.debug(f"Messages found i=={i} length=={len(oldmessages)}")
                    log.debug(f"Messages found j=={j} length=={len(oldmessages)}")
                    filteredArray = oldmessages[i:j]

                log.info(
                    f"""
Setting initial message scan date for {username} to {arrow.get(after).format('YYYY.MM.DD')}
[yellow]Hint: append ' --after 2000' to command to force scan of all messages + download of new files only[/yellow]
[yellow]Hint: append ' --after 2000 --dupe' to command to force scan of all messages + download/re-download of all files[/yellow]

                """
                )

                IDArray = (
                    list(map(lambda x: x.get("id"), filteredArray))
                    if len(filteredArray) > 0
                    else []
                )
                postedAtArray = (
                    list(map(lambda x: x.get("date"), filteredArray))
                    if len(filteredArray) > 0
                    else []
                )

                if len(IDArray) <= 2:
                    tasks.append(
                        asyncio.create_task(
                            scrape_messages(c, model_id, job_progress, message_id=None)
                        )
                    )

                elif len(IDArray) >= min_posts + 1:
                    splitArraysID = [
                        IDArray[i : i + min_posts]
                        for i in range(0, len(IDArray), min_posts)
                    ]
                    splitArraysTime = [
                        postedAtArray[i : i + min_posts]
                        for i in range(0, len(postedAtArray), min_posts)
                    ]

                    # use the previous split for message_id
                    if i == 0:
                        tasks.append(
                            asyncio.create_task(
                                scrape_messages(
                                    c,
                                    model_id,
                                    job_progress,
                                    message_id=None,
                                    required_ids=set(splitArraysTime[0]),
                                )
                            )
                        )
                    else:
                        tasks.append(
                            asyncio.create_task(
                                scrape_messages(
                                    c,
                                    model_id,
                                    job_progress,
                                    message_id=splitArraysID[0][0],
                                    required_ids=set(splitArraysTime[0]),
                                )
                            )
                        )
                    if len(IDArray) >= (min_posts * 2) + 1:
                        [
                            tasks.append(
                                asyncio.create_task(
                                    scrape_messages(
                                        c,
                                        model_id,
                                        job_progress,
                                        required_ids=set(splitArraysTime[i]),
                                        message_id=splitArraysID[i - 1][-1],
                                    )
                                )
                            )
                            for i in range(1, len(splitArraysID) - 1)
                        ]
                        # keeping grabbing until nothing left
                        tasks.append(
                            asyncio.create_task(
                                scrape_messages(
                                    c,
                                    model_id,
                                    job_progress,
                                    message_id=splitArraysID[-2][-1],
                                )
                            )
                        )
                    else:
                        tasks.append(
                            asyncio.create_task(
                                scrape_messages(
                                    c,
                                    model_id,
                                    job_progress,
                                    message_id=splitArraysID[-1][-1],
                                )
                            )
                        )
                else:
                    tasks.append(
                        asyncio.create_task(
                            scrape_messages(
                                c,
                                model_id,
                                job_progress,
                                message_id=IDArray[0],
                                required_ids=set(postedAtArray[1:]),
                            )
                        )
                    )

                page_task = overall_progress.add_task(
                    f" Pages Progress: {page_count}", visible=True
                )

                while tasks:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for result in done:
                        try:
                            out = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        responseArray.extend(out)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
                overall_progress.remove_task(page_task)

        unduped = {}
        log.debug(f"[bold]Messages Count with Dupes[/bold] {len(responseArray)} found")

        for message in responseArray:
            id = message["id"]
            if unduped.get(id):
                continue
            unduped[id] = message

        log.trace(f"messages dupeset messageids {unduped.keys()}")
        log.trace(
            "messages raw unduped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"undupedinfo message: {str(x)}", unduped))
                )
            )
        )
        return list(unduped.values())


@retry(
    retry=retry_if_not_exception_type(KeyboardInterrupt),
    stop=stop_after_attempt(constants.NUM_TRIES),
    wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),
    reraise=True,
)
async def scrape_messages(
    c, model_id, progress, message_id=None, required_ids=None
) -> list:
    global sem
    global tasks
    messages = None
    attempt.set(attempt.get(0) + 1)
    ep = constants.messagesNextEP if message_id else constants.messagesEP
    url = ep.format(model_id, message_id)
    log.debug(f"{message_id if message_id else 'init'}{url}")
    try:
        await sem.acquire()
        async with c.requests(url=url)() as r:
            task = progress.add_task(
                f"Attempt {attempt.get()}/{constants.NUM_TRIES}: Message ID-> {message_id if message_id else 'initial'}"
            )
            if r.ok:
                messages = (await r.json_())["list"]
                log_id = f"offset messageid:{message_id if message_id else 'init id'}"
                if not messages:
                    messages = []
                if len(messages) == 0:
                    log.debug(f"{log_id} -> number of messages found 0")
                elif len(messages) > 0:
                    log.debug(f"{log_id} -> number of messages found {len(messages)}")
                    log.debug(
                        f"{log_id} -> first date {messages[-1].get('createdAt') or messages[0].get('postedAt')}"
                    )
                    log.debug(
                        f"{log_id} -> last date {messages[-1].get('createdAt') or messages[0].get('postedAt')}"
                    )
                    log.debug(
                        f"{log_id} -> found message ids {list(map(lambda x:x.get('id'),messages))}"
                    )
                    log.trace(
                        "{log_id} -> messages raw {posts}".format(
                            log_id=log_id,
                            posts="\n\n".join(
                                list(
                                    map(
                                        lambda x: f" messages scrapeinfo: {str(x)}",
                                        messages,
                                    )
                                )
                            ),
                        )
                    )
                    timestamp = arrow.get(
                        messages[-1].get("createdAt") or messages[-1].get("postedAt")
                    ).float_timestamp

                    if timestamp < after:
                        attempt.set(0)
                    elif required_ids == None:
                        attempt.set(0)
                        new_tasks.append(
                            asyncio.create_task(
                                scrape_messages(
                                    c, model_id, progress, message_id=messages[-1]["id"]
                                )
                            )
                        )
                    else:
                        [
                            required_ids.discard(
                                ele.get("createdAt") or ele.get("postedAt")
                            )
                            for ele in messages
                        ]

                        if len(required_ids) > 0 and timestamp > min(
                            list(required_ids)
                        ):
                            attempt.set(0)
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_messages(
                                        c,
                                        model_id,
                                        progress,
                                        message_id=messages[-1]["id"],
                                        required_ids=required_ids,
                                    )
                                )
                            )
                progress.remove_task(task)

            else:
                log.debug(f"[bold]message response status code:[/bold]{r.status}")
                log.debug(f"[bold]message response:[/bold] {await r.text_()}")
                log.debug(f"[bold]message headers:[/bold] {r.headers}")

                progress.remove_task(task)
                r.raise_for_status()
    except Exception as E:
        raise E
    finally:
        sem.release()
    return messages


def get_individual_post(model_id, postid, c=None):
    with c.requests(url=constants.messageSPECIFIC.format(model_id, postid))() as r:
        if r.ok:
            log.trace(f"message raw individual {r.json()}")
            return r.json()["list"][0]
        else:
            log.debug(f"[bold]invidual message response status code:[/bold]{r.status}")
            log.debug(f"[bold]invidual message  response:[/bold] {r.text_()}")
            log.debug(f"[bold]invidual message  headers:[/bold] {r.headers}")


def get_after(model_id, username):
    cache = Cache(getcachepath(), disk=config_.get_cache_mode(config_.read_config()))
    if args_.getargs().after:
        return args_.getargs().after.float_timestamp
    if cache.get(f"{model_id}_scrape_messages"):
        log.debug(
            "Used after previously scraping entire timeline to make sure content is not missing"
        )
        return 0
    curr = operations.get_messages_media(model_id=model_id, username=username)
    if len(curr) == 0:
        log.debug("Setting date to zero because database is empty")
        return 0
    missing_items = list(filter(lambda x: x[10] != 1, curr))
    missing_items = list(sorted(missing_items, key=lambda x: arrow.get(x[12])))
    if len(missing_items) == 0:
        log.debug(
            "Using last db date because,all downloads in db are marked as downloaded"
        )
        return arrow.get(
            operations.get_last_message_date(model_id=model_id, username=username)
        ).float_timestamp
    else:
        log.debug(
            f"Setting date slightly before earliest missing item\nbecause {len(missing_items)} messages in db are marked as undownloaded"
        )
        return arrow.get(missing_items[0][-1]).float_timestamp - 1000
