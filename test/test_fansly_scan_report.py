"""The Fansly timeline check: after a whole timeline scan, what was found is
logged next to the counts Fansly shows on the profile, with the reasons
anything couldn't be used. No request is sent anywhere."""

import asyncio
import contextlib
import logging

import pytest

from ofscraper.sites.fansly import normalize, scrape
from test.test_fansly_page_generators import (  # noqa: F401 (fixture)
    BASE_TIME,
    CREATOR_ID,
    FakeSession,
    envelope,
    fansly,
    image,
)

pytestmark = pytest.mark.usefixtures("fansly")

STATS = {"imageCount": 3, "videoCount": 0, "bundleImageCount": 2, "bundleVideoCount": 0, "bundleCount": 1}


def post(post_id, *attachments):
    return {
        "id": str(post_id),
        "createdAt": BASE_TIME - post_id,
        "attachments": [
            {"contentType": kind, "contentId": str(cid), "pos": i}
            for i, (kind, cid) in enumerate(attachments)
        ],
    }


PAGES = {
    "0": {
        "posts": [
            post(30, (1, 1001)),
            # one embedded, one fetched separately, one Fansly never returns
            post(29, (2, 77)),
            # a missing bundle and a poll (not media)
            post(28, (2, 78), (7, 5)),
        ],
        "accountMedia": [image(1001), image(1002)],
        "accountMediaBundles": [{"id": "77", "accountMediaIds": ["1002", "1003", "1004"]}],
    },
    "28": {"posts": [post(27, (1, 1001))], "accountMedia": [image(1001)], "accountMediaBundles": []},
    "27": {"posts": []},
}


def route(path, query):
    if path.startswith("timelinenew/"):
        return envelope(PAGES[query["before"]])
    if path == "account/media":
        # Fansly answers only part of what's asked for
        return envelope([image(1003)])
    if path == "account":
        return envelope([{"id": str(CREATOR_ID), "timelineStats": STATS}])
    raise AssertionError(f"unexpected Fansly call {path}")


def test_a_whole_scan_logs_the_check(caplog):
    c = FakeSession(route)

    async def go():
        async with contextlib.aclosing(scrape.timeline_pages(CREATOR_ID, "a creator", c=c)) as gen:
            return [page async for page in gen]

    with caplog.at_level(logging.INFO, logger="shared"):
        pages = asyncio.run(go())

    assert [len(p) for p in pages] == [3, 1]
    (summary,) = [r.getMessage() for r in caplog.records if "timeline check" in r.getMessage()]
    # the 2 bundled images are among the 3, as the scan's 3 distinct photos show
    assert "Fansly counts: 3 images (2 of them in bundles)" in summary
    assert "scan found 4 posts" in summary
    # 1001 twice, 1002 and 1003 from the bundle
    assert "photos: 3 distinct (0 locked), 4 counting repeats" in summary
    assert "bundle media fetched separately: 1 of 2 returned" in summary
    assert "1 x bundle member Fansly didn't send" in summary
    assert "1 x bundle Fansly didn't send" in summary
    assert "1 x attachment type 7 (not media)" in summary


def test_a_scan_stopped_early_logs_nothing(caplog):
    # the pipeline stops once the rest is downloaded: partial counts would mislead
    c = FakeSession(route)

    async def go():
        async with contextlib.aclosing(scrape.timeline_pages(CREATOR_ID, "a creator", c=c)) as gen:
            async for _ in gen:
                break

    with caplog.at_level(logging.INFO, logger="shared"):
        asyncio.run(go())
    assert not [r for r in caplog.records if "timeline check" in r.getMessage()]
    assert "account" not in c.paths()


def test_counts_that_cannot_be_read_still_give_the_check(caplog):
    def no_stats(path, query):
        if path == "account":
            raise RuntimeError("account lookup failed")
        return route(path, query)

    c = FakeSession(no_stats)

    async def go():
        return [p async for p in scrape.timeline_pages(CREATOR_ID, "a creator", c=c)]

    with caplog.at_level(logging.INFO, logger="shared"):
        asyncio.run(go())
    (summary,) = [r.getMessage() for r in caplog.records if "timeline check" in r.getMessage()]
    assert "Fansly counts: not available" in summary


def test_normalize_without_a_report_is_unchanged():
    response = PAGES["0"]
    assert normalize.posts(response) == normalize.posts(response, report=normalize.ScanReport())
