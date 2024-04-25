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
import contextvars
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.style import Style

import ofscraper.classes.sessionmanager as sessionManager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
from ofscraper.utils.context.run_async import run
from ofscraper.utils.logs.helpers import is_trace

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")


@run
async def get_otherlist():
    out = []
    if any(
        [
            ele
            not in [
                constants.getattr("OFSCRAPER_RESERVED_LIST"),
                constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
            ]
            for ele in read_args.retriveArgs().user_list or []
        ]
    ):
        out.extend(await get_lists())
    out = list(
        filter(
            lambda x: x.get("name").lower() in read_args.retriveArgs().user_list or [],
            out,
        )
    )
    log.debug(
        f"User lists found on profile {list(map(lambda x:x.get('name').lower(),out))}"
    )
    return await get_list_users(out)


@run
async def get_blacklist():
    out = []
    if len(read_args.retriveArgs().black_list or []) >= 1:
        out.extend(await get_lists())
    out = list(
        filter(
            lambda x: x.get("name").lower() in read_args.retriveArgs().black_list or [],
            out,
        )
    )
    log.debug(
        f"Black lists found on profile {list(map(lambda x:x.get('name').lower(),out))}"
    )
    names = list(await get_list_users(out))
    return set(list(map(lambda x: x["id"], names)))


async def get_lists():
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting lists...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        tasks = []
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionManager.sessionManager(
                sem=constants.getattr("SUBSCRIPTION_SEMS"),
                retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
                new_request_auth=True,
            ) as c:
                tasks.append(asyncio.create_task(scrape_for_list(c, job_progress)))
                page_task = overall_progress.add_task(
                    f"UserList Pages Progress: {page_count}", visible=True
                )
                while tasks:
                    new_tasks = []
                    for task in asyncio.as_completed(tasks):
                        try:
                            result, new_tasks_batch = await task
                            new_tasks.extend(new_tasks_batch)
                            page_count = page_count + 1
                            overall_progress.update(
                                page_task,
                                description=f"UserList Pages Progress: {page_count}",
                            )
                            output.extend(result)
                        except Exception as E:
                            log.traceback_(E)
                            log.traceback_(traceback.format_exc())
                            continue
                    tasks = new_tasks
    overall_progress.remove_task(page_task)
    trace_log_list(output)

    log.debug(f"[bold]lists name count without Dupes[/bold] {len(output)} found")
    return output


def trace_log_list(responseArray):
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
            "list unduped {posts}".format(
                posts="\n\n".join(map(lambda x: f" list data raw:{x}", chunk))
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


async def scrape_for_list(c, job_progress, offset=0):
    attempt.set(0)
    new_tasks = []
    url = constants.getattr("listEP").format(offset)
    try:
        attempt.set(attempt.get(0) + 1)
        task = job_progress.add_task(
            f" : getting lists offset -> {offset}",
            visible=True,
        )
        async with c.requests_async(url=url) as r:
            data = await r.json_()
            out_list = data["list"] or []
            log.debug(
                f"offset:{offset} -> lists names found {list(map(lambda x:x['name'],out_list))}"
            )
            log.debug(f"offset:{offset} -> number of lists found {len(out_list)}")
            log.debug(
                f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            log.trace(
                "offset:{offset} -> list names raw: {posts}".format(
                    offset=offset, posts=data
                )
            )

            if data.get("hasMore") and len(out_list) > 0:
                offset = offset + len(out_list)
                new_tasks.append(
                    asyncio.create_task(scrape_for_list(c, job_progress, offset=offset))
                )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task)
    return out_list, new_tasks


async def get_list_users(lists):
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_THREAD_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn(
                "Getting users from lists (this may take awhile)...\n{task.description}"
            ),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        tasks = []
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionManager.sessionManager(
                sem=constants.getattr("SUBSCRIPTION_SEMS"),
                retries=constants.getattr("API_INDVIDIUAL_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
                new_request_auth=True,
            ) as c:
                [
                    tasks.append(
                        asyncio.create_task(scrape_list_members(c, id, job_progress))
                    )
                    for id in lists
                ]
                page_task = overall_progress.add_task(
                    f"UserList Users Pages Progress: {page_count}", visible=True
                )
                while tasks:
                    new_tasks = []
                    for task in asyncio.as_completed(tasks):
                        try:
                            result, new_tasks_batch = await task
                            new_tasks.extend(new_tasks_batch)
                            page_count = page_count + 1
                            overall_progress.update(
                                page_task,
                                description=f"UserList Users Pages Progress: {page_count}",
                            )
                            output.extend(result)
                        except Exception as E:
                            log.traceback_(E)
                            log.traceback_(traceback.format_exc())
                            continue
                    tasks = new_tasks

    overall_progress.remove_task(page_task)
    outdict = {}
    for ele in output:
        outdict[ele["id"]] = ele
    trace_log_usernames(outdict.values())
    log.debug(f"[bold]users count without Dupes[/bold] {len(outdict.values())} found")
    return outdict.values()


def trace_log_usernames(responseArray):
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
            "users found {users}".format(
                users="\n\n".join(map(lambda x: f"user data: {str(x)}", chunk))
            )
        )
        # Check if there are more elements remaining after this chunk
        if i + chunk_size > len(responseArray):
            break  # Exit the loop if we've processed all elements


async def scrape_list_members(c, item, job_progress, offset=0):
    users = None
    attempt.set(0)
    new_tasks = []
    url = constants.getattr("listusersEP").format(item.get("id"), offset)
    try:
        attempt.set(attempt.get(0) + 1)
        task = job_progress.add_task(
            f" : offset -> {offset} + list name -> {item.get('name')}",
            visible=True,
        )

        async with c.requests_async(url=url) as r:
            log_id = f"offset:{offset} list:{item.get('name')} =>"
            data = await r.json_()
            users = data.get("list") or []
            log.debug(f"{log_id} -> names found {len(users)}")
            log.debug(
                f"{log_id}  -> hasMore value in json {data.get('hasMore','undefined') }"
            )
            log.debug(
                f"usernames {log_id} : usernames retrived -> {list(map(lambda x:x.get('username'),users))}"
            )
            log.trace(
                "offset: {offset} list: {item} -> {posts}".format(
                    item=item.get("name"),
                    offset=offset,
                    posts="\n\n".join(
                        map(lambda x: f"scrapeinfo list {str(x)}", users)
                    ),
                )
            )
            if (
                data.get("hasMore")
                and len(users) > 0
                and offset != data.get("nextOffset")
            ):
                offset += len(users)
                new_tasks.append(
                    asyncio.create_task(
                        scrape_list_members(c, item, job_progress, offset=offset)
                    )
                )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task)
    return users, new_tasks
