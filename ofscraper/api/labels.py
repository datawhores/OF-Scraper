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
attempt = contextvars.ContextVar("attempt")
sem = None


@run
async def get_labels(model_id):
    global sem
    sem = semaphoreDelayed(constants.getattr("MAX_SEMAPHORE"))
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting labels...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = []
        global tasks
        global new_tasks
        tasks = []
        new_tasks = []

        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionbuilder.sessionBuilder() as c:
                tasks.append(
                    asyncio.create_task(scrape_labels(c, model_id, job_progress))
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
            "post label names unduped {posts}".format(
                posts="\n\n".join(map(lambda x: f" label name unduped:{x}", output))
            )
        )
        log.debug(f"[bold]Labels name count without Dupes[/bold] {len(output)} found")
        return output


async def scrape_labels(c, model_id, job_progress, offset=0):
    global sem
    global tasks
    labels = None
    attempt.set(0)

    async for _ in AsyncRetrying(
        stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
        retry=retry_if_not_exception_type(KeyboardInterrupt),
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
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} {offset}",
                    visible=True,
                )
                async with c.requests(
                    url=constants.getattr("labelsEP").format(model_id, offset)
                )() as r:
                    if r.ok:
                        data = await r.json_()
                        labels = list(
                            filter(lambda x: isinstance(x, list), data.values())
                        )[0]
                        log.debug(
                            f"offset:{offset} -> labels names found {len(labels)}"
                        )
                        log.debug(
                            f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
                        )
                        log.trace(
                            "offset:{offset} -> label names raw: {posts}".format(
                                offset=offset, posts=data
                            )
                        )

                        if data.get("hasMore"):
                            offset = data.get("nextOffset")
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_labels(
                                        c, model_id, job_progress, offset=offset
                                    )
                                )
                            )
                        return data.get("list")

                    else:
                        log.debug(
                            f"[bold]labels response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]labels response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]labels headers:[/bold] {r.headers}")
                        job_progress.remove_task(task)
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)


@run
async def get_labelled_posts(labels, username):
    global sem
    sem = semaphoreDelayed(constants.getattr("MAX_SEMAPHORE"))
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting posts from labels...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        output = {}
        global tasks
        global new_tasks
        tasks = []
        new_tasks
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionbuilder.sessionBuilder() as c:
                [
                    tasks.append(
                        asyncio.create_task(
                            scrape_labelled_posts(c, label, username, job_progress)
                        )
                    )
                    for label in labels
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
                            label, posts = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        label_id_ = label["id"]
                        log.debug(
                            f"[bold]Label {label['name']} post count with Dupes[/bold] {len(posts)} found"
                        )
                        posts = label_dedupe(posts)
                        log.debug(
                            f"[bold]Label {label['name']} post count without Dupes[/bold] {len(posts)} found"
                        )

                        label_ = output.get(label_id_, None)
                        if not label_:
                            output[label_id_] = label
                            output[label_id_]["posts"] = posts
                        else:
                            output[label_id_]["posts"].extend(posts)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
                overall_progress.remove_task(page_task)
        log.trace(
            "post label joined {posts}".format(
                posts="\n\n".join(
                    list(
                        map(
                            lambda x: f"label post joined: {str(x)}",
                            list(output.values()),
                        )
                    )
                )
            )
        )
        log.debug(f"[bold]Labels count without Dupes[/bold] {len(output)} found")

        return list(output.values())


def label_dedupe(posts):
    unduped = {}
    for post in posts:
        id = post["id"]
        if unduped.get(id):
            continue
        unduped[id] = post
    return list(unduped.values())


async def scrape_labelled_posts(c, label, model_id, job_progress, offset=0):
    global sem
    global tasks
    posts = None
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
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} : label -> {label['name']}",
                    visible=True,
                )
                async with c.requests(
                    url=constants.getattr("labelledPostsEP").format(
                        model_id, offset, label["id"]
                    )
                )() as r:
                    if r.ok:
                        data = await r.json_()
                        posts = list(
                            filter(lambda x: isinstance(x, list), data.values())
                        )[0]
                        log.debug(
                            f"offset:{offset} -> labelled posts found {len(posts)}"
                        )
                        log.debug(
                            f"offset:{offset} -> hasMore value in json {data.get('hasMore','undefined') }"
                        )
                        log.trace(
                            "{offset} -> {posts}".format(
                                offset=offset,
                                posts="\n\n".join(
                                    list(
                                        map(
                                            lambda x: f"scrapeinfo label {str(x)}",
                                            posts,
                                        )
                                    )
                                ),
                            )
                        )
                        if data.get("hasMore"):
                            offset += len(posts)
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_labelled_posts(
                                        c, label, model_id, job_progress, offset=offset
                                    )
                                )
                            )

                    else:
                        log.debug(
                            f"[bold]labelled posts response status code:[/bold]{r.status}"
                        )
                        log.debug(
                            f"[bold]labelled posts response:[/bold] {await r.text_()}"
                        )
                        log.debug(f"[bold]labelled posts headers:[/bold] {r.headers}")

                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task)

            return label, posts
