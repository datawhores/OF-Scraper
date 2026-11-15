"""Merge the pages that an area's concurrent workers yield.

Each worker is an async generator of pages. One producer task per worker
feeds a shared queue; the caller's ``on_page`` sees every non-empty page as
it arrives, and the area's pages progress bar counts every page, empty ones
included. A worker that raises is logged and ends; the others carry on.
"""

import asyncio
import logging
import traceback

import ofscraper.utils.live.updater as progress_utils
from ofscraper.commands.scraper.actions.download import stop

log = logging.getLogger("shared")


def post_id(item):
    return item.get("id")


async def consume_pages(generators, description, on_page, progress=None, create_task=None):
    """Run a producer per generator and hand each non-empty page to ``on_page``.

    ``description`` is the progress bar's text; the page count is appended.
    Workers are stop-tracked fetch tasks (``stop.create_fetch_task``) unless
    ``create_task`` says otherwise. ``progress`` defaults to the API screen.
    """
    progress = progress or progress_utils.api
    create_task = create_task or stop.create_fetch_task
    page_count = 0
    page_task = progress.add_overall_task(f"{description}: {page_count}", visible=True)
    queue = asyncio.Queue()

    async def producer(gen):
        try:
            async for page in gen:
                await queue.put(page)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
        finally:
            await queue.put(None)

    workers = [create_task(producer(gen)) for gen in generators]
    active_workers = len(workers)

    while active_workers > 0:
        page = await queue.get()
        if page is None:
            active_workers -= 1
            continue
        page_count += 1
        progress.update_overall_task(
            page_task, description=f"{description}: {page_count}"
        )
        if page:
            on_page(page)

    progress.remove_overall_task(page_task)


async def collect_pages(generators, description, on_new=None, key=post_id, **kwargs):
    """Merge every worker's pages into one list.

    Items whose ``key`` was already seen are dropped (``key=None`` keeps them
    all). ``on_new`` is called with each page's kept items, for logging.
    """
    output = []
    seen = set()

    def on_page(page):
        if key is None:
            new = page
        else:
            new = [x for x in page if key(x) not in seen and not seen.add(key(x))]
        output.extend(new)
        if on_new:
            on_new(new)

    await consume_pages(generators, description, on_page, **kwargs)
    return output
