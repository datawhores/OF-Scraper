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


import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_utils
from ofscraper.utils.context.run_async import run
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log

log = logging.getLogger("shared")
API = "Pinned"


@run
async def get_pinned_posts(model_id, c=None, post_id=None):
    post_id = post_id or []
    # 1. build the list of raw generators
    generators = [scrape_pinned_posts(c, model_id)]

    # 2. process them through the Queue engine
    data = await process_tasks_batch(generators)
    return data


async def process_tasks_batch(generators):
    """
    Fixed Orchestrator: Bridges Async Generators to the event loop
    via a Producer-Consumer Queue.
    """
    responseArray = []
    page_count = 0
    seen = set()
    queue = asyncio.Queue()

    page_task = progress_utils.api.add_overall_task(
        f"Pinned Content Pages Progress: {page_count}", visible=True
    )

    # The Producer: Feeds the queue batches from the generator
    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    # Start producers concurrently
    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    # The Consumer: Aggregates data in real-time
    while active_workers > 0:
        batch = await queue.get()

        if batch is None:
            active_workers -= 1
            continue

        page_count += 1
        progress_utils.api.update_overall_task(
            page_task,
            description=f"Pinned Content Pages Progress: {page_count}",
        )

        if batch:
            new_posts = [
                post
                for post in batch
                if post.get("id") not in seen and not seen.add(post.get("id"))
            ]
            log.debug(
                f"{common_logs.PROGRESS_IDS.format('Pinned')} {list(map(lambda x:x['id'],new_posts))}"
            )
            trace_progress_log(f"{API} task", new_posts)
            responseArray.extend(new_posts)

    progress_utils.api.remove_overall_task(page_task)

    log.debug(
        f"{common_logs.FINAL_IDS.format('Pinned')} {list(map(lambda x:x['id'],responseArray))}"
    )
    trace_log_raw(f"{API} final", responseArray, final_count=True)
    log.debug(common_logs.FINAL_COUNT_POST.format("Pinned", len(responseArray)))
    return responseArray


async def scrape_pinned_posts(c, model_id, offset=0):
    """
    Worker Loop for pinned posts.
    Yields batches page-by-page with safety checks for the EP constant.
    """
    current_offset = offset

    while True:
        # Safety check: Ensure the endpoint string exists before calling .format()
        ep = of_env.getattr("timelinePinnedEP")
        url = ep.format(model_id, current_offset)
        task = None
        try:
            task = progress_utils.api.add_job_task(
                f"[Pinned] offset -> {current_offset}", visible=True
            )
            async with c.requests_async(url=url) as r:
                if not (200 <= r.status < 300):
                    log.debug(f"Pinned API Error: {r.status}")
                    break

                data = await r.json_()
                if not isinstance(data, dict):
                    break

                batch = data.get("list", [])
                if not batch:
                    break

                yield batch

                trace_progress_log(f"{API} request", batch)

                if not data.get("hasMore"):
                    break

                current_offset += len(batch)

        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)
