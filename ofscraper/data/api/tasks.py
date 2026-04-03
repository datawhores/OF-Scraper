import asyncio
import logging
import traceback

import ofscraper.utils.live.updater as progress_utils
import ofscraper.data.api.common.logs.strings as common_logs
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log

log = logging.getLogger("shared")

async def process_tasks(generators, api_type):
    """
    Universal async generator consumer for API requests.
    """
    responseArray = []
    page_count = 0
    seen = set()
    queue = asyncio.Queue()

    page_task = progress_utils.api.add_overall_task(
        f"{api_type} Content Pages Progress: {page_count}", visible=True
    )

    async def producer(gen):
        try:
            async for batch in gen:
                await queue.put(batch)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [asyncio.create_task(producer(g)) for g in generators]
    active_workers = len(workers)

    while active_workers > 0:
        batch = await queue.get()
        if batch is None:
            active_workers -= 1
            continue

        page_count += 1
        progress_utils.api.update_overall_task(
            page_task,
            description=f"{api_type} Content Pages Progress: {page_count}",
        )

        if batch:
            new_posts = [
                post
                for post in batch
                if post.get("id") not in seen and not seen.add(post.get("id"))
            ]
            log.debug(
                f"{common_logs.PROGRESS_IDS.format(api_type)} {list(map(lambda x:x['id'],new_posts))}"
            )
            trace_progress_log(f"{api_type} task", new_posts)
            responseArray.extend(new_posts)

    progress_utils.api.remove_overall_task(page_task)
    
    # Universal Final Logging
    trace_log_raw(f"{api_type} final", responseArray, final_count=True)
    log.debug(common_logs.FINAL_COUNT_POST.format(api_type, len(responseArray)))
    
    return responseArray