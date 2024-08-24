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

import  ofscraper.runner.manager as manager2
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.utils.live.updater import add_userlist_task
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log


log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
API = "USER_LIST"


@run
async def get_otherlist():
    out = []
    if not any(
        [
            ele
            not in [
                constants.getattr("OFSCRAPER_RESERVED_LIST"),
                constants.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
            ]
            for ele in read_args.retriveArgs().user_list or []
        ]
    ):
        return []
    with progress_utils.setup_subscription_progress_live():
        out.extend(await get_lists())
        out = list(
            filter(
                lambda x: x.get("name").lower() in read_args.retriveArgs().user_list
                or [],
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
    if not read_args.retriveArgs().black_list:
        return []
    with progress_utils.setup_subscription_progress_live():
        if len(read_args.retriveArgs().black_list or []) >= 1:
            out.extend(await get_lists())
        out = list(
            filter(
                lambda x: x.get("name").lower() in read_args.retriveArgs().black_list
                or [],
                out,
            )
        )
        log.debug(
            f"Black lists found on profile {list(map(lambda x:x.get('name').lower(),out))}"
        )
        names = list(await get_list_users(out))
    return set(list(map(lambda x: x["id"], names)))


async def get_lists():

    output = []
    tasks = []
    page_count = 0
    async with manager2.Manager.aget_ofsession(
        sem_count=constants.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        tasks.append(asyncio.create_task(scrape_for_list(c)))
        page_task = add_userlist_task(
            f"UserList Pages Progress: {page_count}", visible=True
        )
        while tasks:
            new_tasks = []
            for task in asyncio.as_completed(tasks):
                try:
                    result, new_tasks_batch = await task
                    new_tasks.extend(new_tasks_batch)
                    page_count = page_count + 1
                    progress_updater.update_userlist_task(
                        page_task,
                        description=f"UserList Pages Progress: {page_count}",
                    )
                    output.extend(result)
                except Exception as E:
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    continue
            tasks = new_tasks
    progress_updater.remove_userlist_task(page_task)
    trace_log_raw("list raw unduped", output)

    log.debug(f"[bold]lists name count without Dupes[/bold] {len(output)} found")
    return output


async def scrape_for_list(c, offset=0):
    attempt.set(0)
    new_tasks = []
    url = constants.getattr("listEP").format(offset)
    try:
        attempt.set(attempt.get(0) + 1)
        task = progress_updater.add_userlist_job_task(
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

            trace_log_raw("list names raw", data)
            if data.get("hasMore") and len(out_list) > 0:
                offset = offset + len(out_list)
                new_tasks.append(asyncio.create_task(scrape_for_list(c, offset=offset)))
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        progress_updater.remove_userlist_job_task(task)
    return out_list, new_tasks


async def get_list_users(lists):

    output = []
    tasks = []
    page_count = 0
    async with manager2.Manager.aget_ofsession(
        sem_count=constants.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        [tasks.append(asyncio.create_task(scrape_list_members(c, id))) for id in lists]
        page_task = add_userlist_task(
            f"UserList Users Pages Progress: {page_count}", visible=True
        )
        while tasks:
            new_tasks = []
            for task in asyncio.as_completed(tasks):
                try:
                    result, new_tasks_batch = await task
                    new_tasks.extend(new_tasks_batch)
                    page_count = page_count + 1
                    progress_updater.update_userlist_task(
                        page_task,
                        description=f"UserList Users Pages Progress: {page_count}",
                    )
                    output.extend(result)
                except Exception as E:
                    log.traceback_(E)
                    log.traceback_(traceback.format_exc())
                    continue
            tasks = new_tasks

    progress_updater.remove_userlist_task(page_task)
    outdict = {}
    for ele in output:
        outdict[ele["id"]] = ele
    trace_log_raw("raw user data", outdict.values())
    log.debug(f"[bold]users count without Dupes[/bold] {len(outdict.values())} found")
    return outdict.values()


async def scrape_list_members(c, item, offset=0):
    users = None
    attempt.set(0)
    new_tasks = []
    url = constants.getattr("listusersEP").format(item.get("id"), offset)
    try:
        attempt.set(attempt.get(0) + 1)
        task = progress_updater.add_userlist_job_task(
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
            name = f"API {item.get('name')}"
            trace_progress_log(name, data, offset=offset)

            if (
                data.get("hasMore")
                and len(users) > 0
                and offset != data.get("nextOffset")
            ):
                offset += len(users)
                new_tasks.append(
                    asyncio.create_task(scrape_list_members(c, item, offset=offset))
                )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        progress_updater.remove_userlist_job_task(task)
    return users, new_tasks
