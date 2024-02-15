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
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
sem = None
attempt = contextvars.ContextVar("attempt")


@run
async def get_stories_post(model_id):
    global sem
    sem = semaphoreDelayed(1)
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting story media...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        page_count = 0
        global tasks
        global new_tasks
        tasks = []
        new_tasks = []
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionbuilder.sessionBuilder() as c:
                tasks.append(
                    asyncio.create_task(scrape_stories(c, model_id, job_progress))
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
                            result = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        output.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
            overall_progress.remove_task(page_task)
        log.trace(
            "stories raw unduped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"undupedinfo stories: {str(x)}", output))
                )
            )
        )
        log.debug(f"[bold]stories Count with Dupes[/bold] {len(output)} found")
        outdict = {}
        for ele in output:
            outdict[ele["id"]] = ele
        log.debug(
            f"[bold]stories Count with Dupes[/bold] {len(list(outdict.values()))} found"
        )
        return list(outdict.values())


async def scrape_stories(c, user_id, job_progress) -> list:
    global sem
    global tasks
    stories = None
    attempt.set(0)

    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                task = job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} : user id -> {user_id}",
                    visible=True,
                )
                async with c.requests(
                    url=constants.getattr("highlightsWithAStoryEP").format(user_id)
                )() as r:
                    if r.ok:
                        stories = await r.json_()
                        log.debug(
                            f"stories: -> found stories ids {list(map(lambda x:x.get('id'),stories))}"
                        )
                        log.trace(
                            "stories: -> stories raw {posts}".format(
                                posts="\n\n".join(
                                    list(
                                        map(
                                            lambda x: f"scrapeinfo stories: {str(x)}",
                                            stories,
                                        )
                                    )
                                )
                            )
                        )
                    else:
                        log.debug(
                            f"[bold]stories response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]stories response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]stories headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

            return stories


@run
async def get_highlight_post(model_id):
    global sem
    sem = semaphoreDelayed(1)
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)

        async with sessionbuilder.sessionBuilder() as c:
            overall_progress = Progress(
                SpinnerColumn(style=Style(color="blue")),
                TextColumn("Getting highlight list...\n{task.description}"),
            )
            job_progress = Progress("{task.description}")
            progress_group = Group(overall_progress, Panel(Group(job_progress)))

            output = []

            page_count = 0
            global tasks
            global new_tasks
            tasks = []
            new_tasks = []
            with Live(
                progress_group,
                refresh_per_second=5,
                console=console.get_shared_console(),
            ):
                tasks.append(
                    asyncio.create_task(
                        scrape_highlight_list(c, model_id, job_progress)
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
                            result = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        output.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
                overall_progress.remove_task(page_task)

            overall_progress = Progress(
                SpinnerColumn(style=Style(color="blue")),
                TextColumn("Getting highlight...\n{task.description}"),
            )
            job_progress = Progress("{task.description}")
            progress_group = Group(overall_progress, Panel(Group(job_progress)))
            with Live(
                progress_group,
                refresh_per_second=5,
                console=console.get_shared_console(),
            ):
                output2 = []
                page_count = 0
                tasks = []
                new_tasks = []

                [
                    tasks.append(
                        asyncio.create_task(scrape_highlights(c, i, job_progress))
                    )
                    for i in output
                ]
                page_task = overall_progress.add_task(
                    f" Pages Progress: {page_count}", visible=True
                )
                while tasks:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for result in done:
                        try:
                            result = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        output2.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []

        log.trace(
            "highlight raw unduped {posts}".format(
                posts="\n\n".join(
                    list(map(lambda x: f"undupedinfo heighlight: {str(x)}", output))
                )
            )
        )
        log.debug(f"[bold]highlight Count with Dupes[/bold] {len(output2)} found")
        outdict = {}
        for ele in output2:
            outdict[ele["id"]] = ele
        log.debug(
            f"[bold]highlight Count with Dupes[/bold] {len(list(outdict.values()))} found"
        )
        return list(outdict.values())


async def scrape_highlight_list(c, user_id, job_progress, offset=0) -> list:
    global sem
    global tasks
    attempt.set(0)
    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                task = job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} scraping highlight list  offset-> {offset}",
                    visible=True,
                )
                async with c.requests(
                    url=constants.getattr("highlightsWithStoriesEP").format(
                        user_id, offset
                    )
                )() as r:
                    if r.ok:
                        resp_data = await r.json_()
                        log.trace(
                            f"highlights list: -> found highlights list data {resp_data}"
                        )
                        data = get_highlightList(resp_data)
                        log.debug(f"highlights list: -> found list ids {data}")

                    else:
                        log.debug(
                            f"[bold]highlight list response status code:[/bold]{r.status}"
                        )
                        log.debug(
                            f"[bold]highlight list response:[/bold] {await r.text_()}"
                        )
                        log.debug(f"[bold]highlight list headers:[/bold] {r.headers}")
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

            return data


async def scrape_highlights(c, id, job_progress) -> list:
    global sem
    global tasks
    attempt.set(0)
    async for _ in AsyncRetrying(
        retry=retry_if_not_exception_type(KeyboardInterrupt),
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        wait=wait_random(
            min=constants.getattr("OF_MIN"),
            max=constants.getattr("OF_MAX"),
        ),
        reraise=True,
    ):
        with _:
            await sem.acquire()
            try:
                attempt.set(attempt.get(0) + 1)
                task = job_progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} highlights id -> {id}",
                    visible=True,
                )
                async with c.requests(
                    url=constants.getattr("storyEP").format(id)
                )() as r:
                    if r.ok:
                        resp_data = await r.json_()
                        log.trace(f"highlights: -> found highlights data {resp_data}")
                        log.debug(
                            f"highlights: -> found ids {list(map(lambda x:x.get('id'),resp_data['stories']))}"
                        )
                    else:
                        log.debug(f"[bold]highlight status code:[/bold]{r.status}")
                        log.debug(f"[bold]highlight response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]h ighlight headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

            return resp_data["stories"]


def get_highlightList(data):
    for ele in list(filter(lambda x: isinstance(x, list), data.values())):
        if (
            len(
                list(
                    filter(
                        lambda x: isinstance(x.get("id"), int)
                        and data.get("hasMore") != None,
                        ele,
                    )
                )
            )
            > 0
        ):
            return list(map(lambda x: x.get("id"), ele))
    return []


def get_individual_highlights(id, c=None):
    return get_individual_stories(id, c)
    # with c.requests(constants.getattr("highlightSPECIFIC").format(id))() as r:
    #     if r.ok:
    #         log.trace(f"highlight raw highlight individua; {r.json()}")
    #         return r.json()
    #     else:
    #         log.debug(f"[bold]highlight response status code:[/bold]{r.status}")
    #         log.debug(f"[bold]highlightresponse:[/bold] {await r.text_()}")
    #         log.debug(f"[bold]highlight headers:[/bold] {r.headers}")


def get_individual_stories(id, c=None):
    with c.requests(constants.getattr("storiesSPECIFIC").format(id))() as r:
        if r.ok:
            log.trace(f"highlight raw highlight individua; {r.json_()}")
            return r.json()
        else:
            log.debug(f"[bold]highlight response status code:[/bold]{r.status}")
            log.debug(f"[bold]highlightresponse:[/bold] {r.text_()}")
            log.debug(f"[bold]highlight headers:[/bold] {r.headers}")
