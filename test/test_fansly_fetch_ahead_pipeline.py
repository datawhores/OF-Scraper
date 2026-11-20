"""The page-by-page download tells the refresher what is waiting
(sites/fansly/pipeline.py, utils/refresh.py ``FanslyRefresher``).

A refused link fetches new links for every waiting file in one call, but
only for files the refresher knows are waiting. The list downloader
registers its whole list; the pipeline registers each page, and each chunk
of a whole-list run, as it queues them.
"""

import asyncio

import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.download.utils.refresh as refresh

from test_download_handle_one import env  # noqa: F401  (a fixture)
from test_fansly_ordered_links import (  # noqa: F401  (answers is a fixture)
    Collection,
    answers,
    scanned,
)
from test_fansly_pipeline import (  # noqa: F401  (settings_stub, harness are fixtures)
    harness,
    page,
    post_dict,
    settings_stub,
)


def fansly_post(pid, media_ids):
    """A post whose media carry Fansly details, as the Fansly scan gives them."""
    out = post_dict(pid, media_ids)
    for item in out["media"]:
        item["fansly"] = {"accountMediaId": str(item["id"] + 1), "media": {"id": item["id"]}}
    return out


def waiting_at_each_download(harness, ids):
    seen = {}

    def hook(mid):
        async def record(ele):
            seen[mid] = [e.id for e in refresh.fansly_refresher._waiting.values()]

        return record

    for mid in ids:
        harness.on_download[mid] = hook(mid)
    return seen


def test_queued_pages_are_waiting_in_queue_order(harness):
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [
        page(fansly_post(1, [11, 12])),
        page(fansly_post(2, [21])),
    ]
    seen = waiting_at_each_download(harness, [11, 12, 21])
    harness.run()
    assert harness.downloads == [11, 12, 21]
    # the harness's per-file step doesn't mark files done, so each download
    # sees every file queued so far, first page first
    assert seen[11][:2] == [11, 12]
    assert seen[21] == [11, 12, 21]
    # reset when the creator's downloads end
    assert refresh.fansly_refresher._waiting == {}


def test_a_whole_list_run_registers_each_chunk_as_it_is_queued(harness, answers):
    items = scanned(4)  # chunks of 3 (see the answers fixture)
    seen = waiting_at_each_download(harness, [items[0].id, items[3].id])
    harness.run(collection=Collection(items))
    assert seen[items[0].id] == [item.id for item in items[:3]]
    assert seen[items[3].id] == [item.id for item in items]
    assert refresh.fansly_refresher._waiting == {}


def test_a_finished_file_leaves_the_waiting_list(env, monkeypatch):
    """``handle_one`` (the per-file step of both downloaders) marks it done."""
    ele = scanned(1)[0]
    ele.mark_download_succeeded = lambda: None
    refresh.fansly_refresher.reset()
    refresh.fansly_refresher.expect([ele])

    async def download(*args):
        return "images", 0

    monkeypatch.setattr(run_mod, "download", download)
    asyncio.run(run_mod.handle_one((None, ele, 1, "a-creator"), 1, lambda: 1))
    assert refresh.fansly_refresher._waiting == {}
