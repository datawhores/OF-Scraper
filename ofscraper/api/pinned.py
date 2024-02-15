r"""
                                                             
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import contextvars
import logging
import math
import traceback
from concurrent.futures import ThreadPoolExecutor

import arrow
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
import ofscraper.utils.args.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
from ofscraper.utils.context.run_async import run

from ..utils import auth

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
sem = None


async def scrape_pinned_posts(c, model_id, progress, timestamp=None, count=0) -> list:
    global tasks
    global sem
    sem = semaphoreDelayed(constants.getattr("AlT_SEM"))
    posts = None
    attempt.set(0)

    if timestamp and (
        float(timestamp)
        > (read_args.retriveArgs().before or arrow.now()).float_timestamp
    ):
        return []
    url = constants.getattr("timelinePinnedEP").format(model_id, count)
    log.debug(url)

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
                task = progress.add_task(
                    f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')}: Timestamp -> {arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}",
                    visible=True,
                )
                async with c.requests(url=url)() as r:
                    if r.ok:
                        posts = (await r.json_())["list"]
                        posts = list(
                            sorted(posts, key=lambda x: float(x["postedAtPrecise"]))
                        )
                        posts = list(
                            filter(
                                lambda x: float(x["postedAtPrecise"])
                                > float(timestamp or 0),
                                posts,
                            )
                        )
                        log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))) if timestamp!=None  else 'initial'}"
                        if not posts:
                            posts = []
                        if len(posts) == 0:
                            log.debug(f"{log_id} -> number of pinned post found 0")
                        else:
                            log.debug(
                                f"{log_id} -> number of pinned post found {len(posts)}"
                            )
                            log.debug(
                                f"{log_id} -> first date {posts[0].get('createdAt') or posts[0].get('postedAt')}"
                            )
                            log.debug(
                                f"{log_id} -> last date {posts[-1].get('createdAt') or posts[-1].get('postedAt')}"
                            )
                            log.debug(
                                f"{log_id} -> found pinned post IDs {list(map(lambda x:x.get('id'),posts))}"
                            )
                            log.trace(
                                "{log_id} -> pinned raw {posts}".format(
                                    log_id=log_id,
                                    posts="\n\n".join(
                                        list(
                                            map(
                                                lambda x: f"scrapeinfo pinned: {str(x)}",
                                                posts,
                                            )
                                        )
                                    ),
                                )
                            )
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_pinned_posts(
                                        c,
                                        model_id,
                                        progress,
                                        timestamp=posts[-1]["postedAtPrecise"],
                                        count=count + len(posts),
                                    )
                                )
                            )
                    else:
                        log.debug(
                            f"[bold]timeline response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]timeline response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]timeline headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                progress.remove_task(task)
            return posts


@run
async def get_pinned_post(model_id):
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_REQUEST_WORKERS")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        overall_progress = Progress(
            SpinnerColumn(style=Style(color="blue")),
            TextColumn("Getting pinned media...\n{task.description}"),
        )
        job_progress = Progress("{task.description}")
        progress_group = Group(overall_progress, Panel(Group(job_progress)))

        global tasks
        global new_tasks
        tasks = []
        new_tasks = []
        responseArray = []
        page_count = 0
        with Live(
            progress_group, refresh_per_second=5, console=console.get_shared_console()
        ):
            async with sessionbuilder.sessionBuilder() as c:
                tasks.append(
                    asyncio.create_task(
                        scrape_pinned_posts(
                            c,
                            model_id,
                            job_progress,
                            timestamp=read_args.retriveArgs().after.float_timestamp
                            if read_args.retriveArgs().after
                            else None,
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
                            result = await result
                        except Exception as E:
                            log.debug(E)
                            continue
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Pages Progress: {page_count}"
                        )
                        responseArray.extend(result)
                    tasks = list(pending)
                    tasks.extend(new_tasks)
                    new_tasks = []
                overall_progress.remove_task(page_task)
        outdict = {}
        log.debug(f"[bold]Pinned Count with Dupes[/bold] {len(responseArray)} found")
        for post in responseArray:
            outdict[post["id"]] = post
        log.trace(f"pinned dupeset postids {outdict.keys()}")
        log.trace(
            "pinned raw unduped {posts}".format(
                posts="\n\n".join(
                    list(
                        map(lambda x: f"undupedinfo pinned: {str(x)}", outdict.values())
                    )
                )
            )
        )
        log.debug(
            f"[bold]Pinned Count without Dupes[/bold] {len(outdict.values())} found"
        )
        return list(outdict.values())
