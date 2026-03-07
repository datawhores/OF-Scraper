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

import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
import ofscraper.utils.settings as settings

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
                of_env.getattr("OFSCRAPER_RESERVED_LIST"),
                of_env.getattr("OFSCRAPER_RESERVED_LIST_ALT"),
            ]
            for ele in settings.get_settings().userlist or []
        ]
    ):
        return []
    with progress_utils.setup_live("user_list"):
        out.extend(await get_lists())
        out = list(
            filter(
                lambda x: x.get("name").lower() in settings.get_settings().userlist
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
    if not settings.get_settings().blacklist:
        return []
    with progress_utils.setup_live("user_list"):
        if len(settings.get_settings().blacklist or []) >= 1:
            out.extend(await get_lists())
        out = list(
            filter(
                lambda x: x.get("name").lower() in settings.get_settings().blacklist
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
    page_count = 0
    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        page_task = progress_updater.userlist.add_overall_task(
            f"UserList Pages Progress: {page_count}", visible=True
        )

        try:
            generator = scrape_for_list(c)
            async for batch in generator:
                page_count += 1
                progress_updater.userlist.update_overall_task(
                    page_task,
                    description=f"UserList Pages Progress: {page_count}",
                )
                output.extend(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())

        progress_updater.userlist.remove_overall_task(page_task)

    trace_log_raw("list raw unduped", output)
    log.debug(f"[bold]lists name count without Dupes[/bold] {len(output)} found")
    return output


async def scrape_for_list(c, offset=0):
    """
    Async Generator Worker for fetching user lists.
    """
    attempt.set(0)
    current_offset = offset

    while True:
        url = of_env.getattr("listEP").format(current_offset)
        task = None
        try:
            attempt.set(attempt.get(0) + 1)
            task = progress_updater.userlist.add_job_task(
                f" : getting lists offset -> {current_offset}",
                visible=True,
            )
            async with c.requests_async(url=url) as r:
                data = await r.json()
                out_list = data["list"] or []
                log.debug(
                    f"offset:{current_offset} -> lists names found {list(map(lambda x:x['name'],out_list))}"
                )
                log.debug(
                    f"offset:{current_offset} -> number of lists found {len(out_list)}"
                )
                log.debug(
                    f"offset:{current_offset} -> hasMore value in json {data.get('hasMore','undefined') }"
                )

                trace_log_raw("list names raw", data)

                # YIELD BATCH
                yield out_list

                # PAGINATION LOGIC
                if not data.get("hasMore") or not out_list:
                    break

                current_offset += len(out_list)

        except asyncio.TimeoutError:
            log.debug(f"Task timed out {url}")
            break
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_updater.userlist.remove_job_task(task)


async def get_list_users(lists):
    output = []
    page_count = 0

    async with manager.Manager.session.aget_subscription_session(
        sem_count=of_env.getattr("SUBSCRIPTION_SEMS"),
    ) as c:
        page_task = progress_updater.userlist.add_overall_task(
            f"UserList Users Pages Progress: {page_count}", visible=True
        )

        # Queue to aggregate results from concurrent generators
        queue = asyncio.Queue()

        async def producer(generator):
            try:
                async for batch in generator:
                    await queue.put(batch)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
            finally:
                await queue.put(None)  # Signal done

        # Start producers for each list
        generators = [scrape_list_members(c, item) for item in lists]
        producers = [asyncio.create_task(producer(gen)) for gen in generators]
        active_producers = len(producers)

        while active_producers > 0:
            item = await queue.get()

            if item is None:
                active_producers -= 1
                continue

            page_count += 1
            progress_updater.userlist.update_overall_task(
                page_task,
                description=f"UserList Users Pages Progress: {page_count}",
            )
            output.extend(item)

        progress_updater.userlist.remove_overall_task(page_task)

    outdict = {}
    for ele in output:
        outdict[ele["id"]] = ele
    trace_log_raw("raw user data", outdict.values())
    log.debug(f"[bold]users count without Dupes[/bold] {len(outdict.values())} found")
    return list(outdict.values())


async def scrape_list_members(c, item, offset=0):
    """
    Async Generator Worker for fetching members of a specific list.
    """
    attempt.set(0)
    current_offset = offset

    while True:
        url = of_env.getattr("listusersEP").format(item.get("id"), current_offset)
        task = None
        try:
            attempt.set(attempt.get(0) + 1)
            task = progress_updater.userlist.add_job_task(
                f" : offset -> {current_offset} + list name -> {item.get('name')}",
                visible=True,
            )

            async with c.requests_async(url=url) as r:
                log_id = f"offset:{current_offset} list:{item.get('name')} =>"
                data = await r.json()
                users = data.get("list") or []

                log.debug(f"{log_id} -> names found {len(users)}")
                log.debug(
                    f"{log_id}  -> hasMore value in json {data.get('hasMore','undefined') }"
                )
                log.debug(
                    f"{log_id}  -> nextOffset value in json {data.get('nextOffset','undefined') }"
                )

                name = f"API {item.get('name')}"
                trace_progress_log(name, data, offset=current_offset)

                # YIELD BATCH
                if users:
                    yield users

                # PAGINATION LOGIC
                if not data.get("hasMore"):
                    break

                if "nextOffset" in data:
                    current_offset = data["nextOffset"]
                else:
                    # Fallback if nextOffset isn't present but hasMore is true
                    current_offset += len(users)

        except asyncio.TimeoutError:
            log.debug(f"Task timed out {url}")
            break
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_updater.userlist.remove_job_task(task)
