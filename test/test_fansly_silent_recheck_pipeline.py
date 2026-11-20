"""The page-by-page download checks silent videos again, as the list
downloader does (download/utils/silent.py, sites/fansly/pipeline.py).

Videos saved without sound because their audio was refused are flagged and
their audio is checked again after a creator's downloads. The list
downloader did that at the end of ``downloader``; Fansly download runs now
go through the pipeline, which has to do it too, with every media the run
scanned, so an accepted video can be downloaded again.
"""

import pytest

from ofscraper.commands.scraper.actions.download import stop

from test_fansly_ordered_links import Collection, scanned
from test_fansly_pipeline import (  # noqa: F401  (settings_stub, harness are fixtures)
    MODEL_ID,
    NAME,
    harness,
    page,
    post_dict,
    settings_stub,
)


def test_silent_videos_are_checked_after_the_downloads_with_every_scanned_media(harness):
    harness.areas = ["Messages", "Timeline"]
    harness.pages["Messages"] = [page(post_dict(5, [51], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [page(post_dict(1, [11, 12])), page(post_dict(2, [21]))]
    harness.downloaded = {12}  # scanned but not downloaded again
    harness.run()
    assert harness.calls["silent recheck"] == [(NAME, MODEL_ID, [51, 11, 12, 21])]
    events = harness.events
    assert events.index("silent recheck") > events.index("download 21")
    assert events.index("silent recheck") < events.index("stats")


def test_a_whole_list_run_checks_them_too(harness):
    items = scanned(2)
    harness.run(collection=Collection(items))
    assert len(harness.calls["silent recheck"]) == 1


def test_a_stopped_run_does_not_check_them(harness):
    async def stop_now(ele):
        stop.request()
        return None

    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [11]))]
    harness.on_download[11] = stop_now
    with pytest.raises(stop.DownloadsStopped):
        harness.run()
    assert "silent recheck" not in harness.events
