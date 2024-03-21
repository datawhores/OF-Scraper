r"""
                                                      o       
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

from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
import ofscraper.utils.sems as sems
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
attempt = contextvars.ContextVar("attempt")
sem = None


@run
async def get_labels(model_id, c=None):
    global sem
    sem = sems.get_req_sem()
    responseArray = []
    tasks = []

    page_count = 0
    job_progress = progress_utils.labelled_progress
    overall_progress = progress_utils.overall_progress

    # async with c or sessionbuilder.sessionBuilder(
    #     limit=constants.getattr("API_MAX_CONNECTION")
    # ) as c:
    tasks.append(
        asyncio.create_task(scrape_labels(c, model_id, job_progress=job_progress))
    )

    page_task = overall_progress.add_task(
        f"Label Names Pages Progresss: {page_count}", visible=True
    )
    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * len(tasks)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        result, new_tasks_batch = await task
                        new_tasks.extend(new_tasks_batch)
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task,
                            description=f"Label Names Pages Progress: {page_count}",
                        )
                        responseArray.extend(result)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
            tasks = new_tasks
        except TimeoutError as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    overall_progress.remove_task(page_task)
    progress_utils.labelled_layout.visible = False
    log.trace(
        "post label names unduped {posts}".format(
            posts="\n\n".join(map(lambda x: f" label name unduped:{x}", responseArray))
        )
    )
    log.debug(
        f"[bold]Labels name count without Dupes[/bold] {len(responseArray)} found"
    )
    return responseArray


async def scrape_labels(c, model_id, job_progress=None, offset=0):
    global sem
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
            new_tasks = []
            await sem.acquire()
            await asyncio.sleep(1)
            try:
                attempt.set(attempt.get(0) + 1)

                task = (
                    job_progress.add_task(
                        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} labels offset -> {offset}",
                        visible=True,
                    )
                    if job_progress
                    else None
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

                        if (
                            data.get("hasMore")
                            and len(data.get("list")) > 0
                            and data.get("nextOffset") != offset
                        ):
                            offset = offset + len(data.get("list"))
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_labels(
                                        c,
                                        model_id,
                                        job_progress=job_progress,
                                        offset=offset,
                                    )
                                )
                            )
                        return data.get("list"), new_tasks

                    else:
                        log.debug(
                            f"[bold]labels response status code:[/bold]{r.status}"
                        )
                        log.debug(f"[bold]labels response:[/bold] {await r.text_()}")
                        log.debug(f"[bold]labels headers:[/bold] {r.headers}")
                        r.raise_for_status()
            except Exception as E:
                await asyncio.sleep(1)

                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task) if job_progress and task else None


@run
async def get_labelled_posts(labels, username, c=None):
    global sem
    sem = sems.get_req_sem()
    responseDict = get_default_label_dict(labels)
    tasks = []
    page_count = 0
    job_progress = progress_utils.labelled_progress
    overall_progress = progress_utils.overall_progress

    # async with c or sessionbuilder.sessionBuilder(
    #     limit=constants.getattr("API_MAX_CONNECTION")
    # ) as c:
    [
        tasks.append(
            asyncio.create_task(
                scrape_labelled_posts(c, label, username, job_progress=job_progress)
            )
        )
        for label in labels
    ]

    page_task = overall_progress.add_task(
        f" Labels Progress: {page_count}", visible=True
    )

    while bool(tasks):
        new_tasks = []
        try:
            async with asyncio.timeout(
                constants.getattr("API_TIMEOUT_PER_TASKS") * len(tasks)
            ):
                for task in asyncio.as_completed(tasks):
                    try:
                        label, new_posts, new_tasks = await task
                        page_count = page_count + 1
                        overall_progress.update(
                            page_task, description=f"Labels Progress: {page_count}"
                        )
                        log.debug(
                            f"[bold]Label {label['name']} new post count with Dupes[/bold] {len(new_posts)} found"
                        )
                        new_posts = label_dedupe(new_posts)
                        log.debug(
                            f"[bold]Label {label['name']} new post count without Dupes[/bold] {len(new_posts)} found"
                        )
                        posts = label_dedupe(
                            responseDict[label["id"]].get("posts", []) + new_posts
                        )
                        responseDict[label["id"]]["posts"] = posts
                        tasks.extend(new_tasks)
                    except Exception as E:
                        log.traceback_(E)
                        log.traceback_(traceback.format_exc())
                        continue
        except TimeoutError as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        tasks = new_tasks
    overall_progress.remove_task(page_task)
    progress_utils.labelled_layout.visible = False

    log.trace(
        "post label joined {posts}".format(
            posts="\n\n".join(
                list(
                    map(
                        lambda x: f"label post joined: {str(x)}",
                        list(responseDict.values()),
                    )
                )
            )
        )
    )
    log.debug(f"[bold]Labels count without Dupes[/bold] {len(responseDict)} found")

    return list(responseDict.values())


async def scrape_labelled_posts(c, label, model_id, job_progress=None, offset=0):
    global sem
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
            new_tasks = []
            await sem.acquire()
            await asyncio.sleep(1)
            try:
                attempt.set(attempt.get(0) + 1)
                task = (
                    job_progress.add_task(
                        f"Attempt {attempt.get()}/{constants.getattr('NUM_TRIES')} : getting posts from label -> {label['name']}",
                        visible=True,
                    )
                    if job_progress
                    else None
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

                        if data.get("hasMore") and len(posts) > 0:
                            offset += len(posts)
                            new_tasks.append(
                                asyncio.create_task(
                                    scrape_labelled_posts(
                                        c,
                                        label,
                                        model_id,
                                        job_progress=job_progress,
                                        offset=offset,
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
                await asyncio.sleep(1)
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                raise E

            finally:
                sem.release()
                job_progress.remove_task(task) if job_progress and task else None

            return label, posts, new_tasks


def label_dedupe(posts):
    unduped = {}
    for post in posts:
        id = post["id"]
        if unduped.get(id):
            continue
        unduped[id] = post
    return list(unduped.values())


def get_default_label_dict(labels):
    output = {}
    for label in labels:
        output[label["id"]] = label
    return output
