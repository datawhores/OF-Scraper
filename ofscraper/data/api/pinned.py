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

import logging
import traceback

import ofscraper.data.api.common.incomplete as incomplete
import ofscraper.data.api.common.logs.strings as common_logs
import ofscraper.utils.live.updater as progress_utils
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.data.api.common.logs.logs import trace_log_raw, trace_progress_log
from ofscraper.data.api.tasks import collect_pages
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")
API = "Pinned"


@run
@stop.fetching
async def get_pinned_posts(model_id, c=None, post_id=None):
    post_id = post_id or []
    # 1. build the list of raw generators
    generators = [scrape_pinned_posts(c, model_id)]

    # 2. process them through the Queue engine
    data = await process_tasks_batch(generators)
    return data


async def process_tasks_batch(generators):
    def on_new(new_posts):
        log.debug(
            f"{common_logs.PROGRESS_IDS.format('Pinned')} {list(map(lambda x:x['id'],new_posts))}"
        )
        trace_progress_log(f"{API} task", new_posts)

    responseArray = await collect_pages(
        generators, "Pinned Content Pages Progress", on_new
    )
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
                    incomplete.mark_incomplete(model_id, API, f"HTTP {r.status}")
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
            incomplete.mark_incomplete(model_id, API, f"{type(E).__name__}: {E}")
            break
        finally:
            if task:
                progress_utils.api.remove_job_task(task)
