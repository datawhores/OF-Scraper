r"""
                                                             
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
                 \/     \/           \/            \/         
"""

import asyncio
import logging
import math
import traceback

import arrow

import ofscraper.api.common.logs as common_logs
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.progress as progress_utils
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@run
async def get_pinned_posts_progress(model_id, c=None):
    tasks = []
    job_progress = progress_utils.pinned_progress
    tasks.append(
        asyncio.create_task(
            scrape_pinned_posts(
                c,
                model_id,
                job_progress=job_progress,
                timestamp=(
                    read_args.retriveArgs().after.float_timestamp
                    if read_args.retriveArgs().after
                    else None
                ),
            )
        )
    )
    data = await process_tasks(tasks, model_id)
    progress_utils.pinned_layout.visible = False
    return data


@run
async def get_pinned_posts(model_id, c=None):
    tasks = []
    with progress_utils.set_up_api_pinned():

        tasks.append(
            asyncio.create_task(
                scrape_pinned_posts(
                    c,
                    model_id,
                    job_progress=progress_utils.pinned_progress,
                    timestamp=(
                        read_args.retriveArgs().after.float_timestamp
                        if read_args.retriveArgs().after
                        else None
                    ),
                )
            )
        )
    return await process_tasks(tasks, model_id)


async def process_tasks(tasks, model_id):
    responseArray = []
    page_count = 0
    overall_progress = progress_utils.overall_progress

    page_task = overall_progress.add_task(
        f"Pinned Content Pages Progress: {page_count}", visible=True
    )
    seen = set()

    while tasks:
        new_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                result, new_tasks_batch = await task
                new_tasks.extend(new_tasks_batch)
                page_count = page_count + 1
                overall_progress.update(
                    page_task,
                    description=f"Pinned Content Pages Progress: {page_count}",
                )
                new_posts = [
                    post
                    for post in result
                    if post["id"] not in seen and not seen.add(post["id"])
                ]
                log.debug(
                    f"{common_logs.PROGRESS_IDS.format('Pinned')} {list(map(lambda x:x['id'],new_posts))}"
                )
                log.trace(
                    f"{common_logs.PROGRESS_RAW.format('Pinned')}".format(
                        posts="\n\n".join(
                            map(
                                lambda x: f"{common_logs.RAW_INNER} {x}",
                                new_posts,
                            )
                        )
                    )
                )

                responseArray.extend(new_posts)
            except Exception as E:
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
                continue
        tasks = new_tasks
    overall_progress.remove_task(page_task)
    log.debug(f"[bold]Pinned Count with Dupes[/bold] {len(responseArray)} found")
    log.trace(
        "pinned raw duped {posts}".format(
            posts="\n\n".join(
                map(lambda x: f"dupedinfo pinned: {str(x)}", responseArray)
            )
        )
    )
    log.debug(
        f"{common_logs.FINAL_IDS.format('Pinned')} {list(map(lambda x:x['id'],responseArray))}"
    )

    pinned_str = ""
    for post in responseArray:
        pinned_str += f"{common_logs.RAW_INNER} {post}\n\n"
    log.trace(f"{common_logs.FINAL_RAW.format('Pinned')}".format(posts=pinned_str))
    log.debug(f"{common_logs.FINAL_COUNT.format('Pinned')} {len(responseArray)}")

    set_check(responseArray, model_id)
    return responseArray


def set_check(unduped, model_id):
    if not read_args.retriveArgs().after:
        seen = set()
        all_posts = [
            post
            for post in cache.get(f"pinned_check_{model_id}", default=[]) + unduped
            if post["id"] not in seen and not seen.add(post["id"])
        ]
        cache.set(
            f"pinned_check_{model_id}",
            all_posts,
            expire=constants.getattr("THREE_DAY_SECONDS"),
        )
        cache.close()


async def scrape_pinned_posts(
    c, model_id, job_progress=None, timestamp=None, count=0
) -> list:
    posts = None

    if timestamp and (
        float(timestamp)
        > (read_args.retriveArgs().before or arrow.now()).float_timestamp
    ):
        return []
    url = constants.getattr("timelinePinnedEP").format(model_id, count)
    log.debug(url)
    new_tasks = []
    await asyncio.sleep(1)
    try:

        task = (
            job_progress.add_task(
                f"Timestamp -> {arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}",
                visible=True,
            )
            if job_progress
            else None
        )
        async with c.requests_async(url=url) as r:
            posts = (await r.json_())["list"]
            posts = list(sorted(posts, key=lambda x: float(x["postedAtPrecise"])))
            posts = list(
                filter(
                    lambda x: float(x["postedAtPrecise"]) > float(timestamp or 0),
                    posts,
                )
            )
            log_id = f"timestamp:{arrow.get(math.trunc(float(timestamp))).format(constants.getattr('API_DATE_FORMAT')) if timestamp is not None  else 'initial'}"
            if not posts:
                posts = []
            if len(posts) == 0:
                log.debug(f"{log_id} -> number of pinned post found 0")
            else:
                log.debug(f"{log_id} -> number of pinned post found {len(posts)}")
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
                            map(
                                lambda x: f"scrapeinfo pinned: {str(x)}",
                                posts,
                            )
                        ),
                    )
                )
                new_tasks.append(
                    asyncio.create_task(
                        scrape_pinned_posts(
                            c,
                            model_id,
                            job_progress=job_progress,
                            timestamp=posts[-1]["postedAtPrecise"],
                            count=count + len(posts),
                        )
                    )
                )
    except asyncio.TimeoutError:
        raise Exception(f"Task timed out {url}")

    except Exception as E:
        await asyncio.sleep(1)
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E

    finally:
        job_progress.remove_task(task) if job_progress and task else None
    return posts, new_tasks
