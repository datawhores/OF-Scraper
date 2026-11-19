"""Fansly repeat runs stop scanning where the last finished scan began
(sites/fansly/incremental.py).

A Fansly run rescanned the whole timeline and every message each time
unless --after was given: about 365 API calls for a large creator at one
call every 6 seconds, even with nothing new. Now each area keeps a mark, the
newest post its last finished page-by-page scan saw, and a repeat run stops
at the first page whose posts are all at or below it, once no post with
media left to download is older than that page. These tests run the real
pipeline in the harness of test_fansly_pipeline.
"""

import asyncio
import time
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.data.api.common.cache.read as cache_read
import ofscraper.sites.fansly.incremental as incremental
import ofscraper.utils.logs.utils.level as level
from ofscraper.commands.scraper.actions.download import stop

from test_fansly_pipeline import (  # noqa: F401  (settings_stub, harness are fixtures)
    MODEL_ID,
    NAME,
    FakeCache,
    harness,
    page,
    post_dict,
    settings_stub,
)

DAY = 24 * 3600


def asked(harness, area):
    return [e for e in harness.events if e.startswith(f"{area} page")]


def timeline_pages(first_post, count, per_page=2):
    """``count`` pages, newest first: higher ids are newer."""
    pages = []
    pid = first_post
    for _ in range(count):
        pages.append(page(*(post_dict(pid - i, [10_000 + pid - i]) for i in range(per_page))))
        pid -= per_page
    return pages


def new_run(harness):
    harness.events.clear()
    harness.downloads.clear()
    harness.calls.clear()


def mark(harness, area="Timeline"):
    return harness.cache.get(incremental.mark_key(MODEL_ID, area))


def age_full_scan(harness, days, area="Timeline"):
    harness.cache[incremental.mark_key(MODEL_ID, area)]["full_at"] -= days * DAY


@pytest.fixture
def repeat(harness):
    """A creator scanned fully once, with three timeline pages and two
    message pages, all downloaded."""
    harness.areas = ["Messages", "Timeline"]
    harness.pages["Timeline"] = timeline_pages(100, 3)
    harness.pages["Messages"] = [
        page(post_dict(60, [20_060], from_user=MODEL_ID)),
        page(post_dict(59, [20_059], from_user=MODEL_ID)),
    ]
    harness.run()
    assert len(asked(harness, "Timeline")) == 3
    assert len(asked(harness, "Messages")) == 2
    harness.downloaded = {10_000 + n for n in range(95, 101)} | {20_060, 20_059}
    new_run(harness)
    return harness


def test_a_repeat_run_with_nothing_new_asks_for_one_page_per_area(repeat):
    repeat.run()
    assert asked(repeat, "Timeline") == ["Timeline page 1"]
    assert asked(repeat, "Messages") == ["Messages page 1"]
    assert repeat.downloads == []
    # stopping early counts as a finished scan
    checked = [args for args, _ in repeat.calls["after check"]]
    assert checked == [(MODEL_ID, "Messages"), (MODEL_ID, "Timeline")]


def test_the_first_run_records_the_newest_post_of_each_downloaded_area(harness):
    harness.areas = ["Messages", "Timeline", "Purchased"]
    harness.pages["Messages"] = [page(post_dict(60, [20_060], from_user=MODEL_ID))]
    harness.pages["Timeline"] = timeline_pages(100, 2)
    harness.pages["Purchased"] = [page(post_dict(500, [10_500]))]
    before = time.time()
    harness.run()
    assert set(harness.cache) == {
        incremental.mark_key(MODEL_ID, "Messages"),
        incremental.mark_key(MODEL_ID, "Timeline"),
    }
    timeline = mark(harness)
    assert (timeline["newest"], timeline["oldest"]) == (100, 97)
    assert timeline["full_at"] == timeline["at"] >= before
    assert mark(harness, "Messages")["newest"] == 60


def test_new_posts_on_the_first_page_scan_to_the_first_page_below_the_mark(repeat):
    # two new posts push the old ones down a page
    repeat.pages["Timeline"] = [
        page(post_dict(102, [10_102]), post_dict(101, [10_101])),
        *timeline_pages(100, 3),
    ]
    repeat.run()
    assert asked(repeat, "Timeline") == ["Timeline page 1", "Timeline page 2"]
    assert repeat.downloads == [10_102, 10_101]
    # the mark moves up; the last full scan stays the first run's
    first_full = mark(repeat)["full_at"]
    assert (mark(repeat)["newest"], mark(repeat)["oldest"]) == (102, 95)
    assert mark(repeat)["full_at"] == first_full


def test_a_post_with_media_left_keeps_the_scan_going_down_to_it(repeat):
    repeat.pages["Timeline"] = timeline_pages(100, 6)
    repeat.recorded["posts"].update(range(89, 95))
    repeat.downloaded |= {10_000 + n for n in range(89, 95)}
    # post 92 is on page 5 and still has media to download
    repeat.pending = {92}
    repeat.downloaded.discard(10_092)
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 5
    assert repeat.downloads == [10_092]


def test_a_stopped_run_leaves_the_mark_as_it_was(repeat):
    async def stop_now(ele):
        stop.request()
        return None

    before = dict(mark(repeat))
    # new posts: the run is stopped while it downloads the first
    repeat.pages["Timeline"] = [
        page(post_dict(102, [10_102]), post_dict(101, [10_101])),
        *timeline_pages(100, 3),
    ]
    repeat.areas = ["Timeline"]
    repeat.on_download[10_102] = stop_now
    with pytest.raises(stop.DownloadsStopped):
        repeat.run()
    stop.clear()
    assert mark(repeat) == before

    # the next run still scans down past the new posts
    new_run(repeat)
    repeat.on_download.clear()
    repeat.run()
    assert asked(repeat, "Timeline") == ["Timeline page 1", "Timeline page 2"]
    assert repeat.downloads == [10_102, 10_101]


def test_a_scan_that_failed_leaves_the_mark_as_it_was(repeat):
    level.addtraceback()  # an area failure logs its traceback at this level
    before = dict(mark(repeat))
    repeat.areas = ["Timeline"]
    new_page = page(post_dict(102, [10_102]), post_dict(101, [10_101]))
    repeat.pages["Timeline"] = [new_page, ValueError("boom")]
    repeat.run()
    assert mark(repeat) == before


def test_a_database_that_was_reset_is_scanned_in_full(repeat):
    # the database is deleted, restored or moved; the profile cache, which
    # holds the marks, stays
    repeat.recorded = {"posts": set(), "messages": set()}
    repeat.downloaded = set()
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert len(asked(repeat, "Messages")) == 2
    assert sorted(repeat.downloads) == [10_095, 10_096, 10_097, 10_098, 10_099, 10_100,
                                        20_059, 20_060]


def test_a_full_scan_stopped_after_a_reset_is_not_taken_for_finished(repeat):
    async def stop_now(ele):
        stop.request()
        return None

    repeat.areas = ["Timeline"]
    repeat.recorded = {"posts": set(), "messages": set()}
    repeat.downloaded = set()
    # stopped on the first file: page 1's rows, the mark's post among them,
    # are in the database again
    repeat.on_download[10_100] = stop_now
    with pytest.raises(stop.DownloadsStopped):
        repeat.run()
    stop.clear()
    assert 100 in repeat.recorded["posts"]
    assert not mark(repeat)

    new_run(repeat)
    repeat.on_download.clear()
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert sorted(repeat.downloads) == [10_095, 10_096, 10_097, 10_098, 10_099, 10_100]


@pytest.mark.parametrize("written_back", ["newest", "page 1"])
def test_a_reset_database_given_its_newest_post_back_is_still_scanned_in_full(
        repeat, written_back):
    # after the reset another kind of run (manual, a purchased-only run, an
    # interrupted scan-first run) writes the creator's newest posts, without
    # scanning page by page: the mark's newest post is in the database again
    back = {"newest": {100}, "page 1": {100, 99}}[written_back]
    repeat.areas = ["Timeline"]
    repeat.recorded = {"posts": set(back), "messages": set()}
    repeat.downloaded = {10_000 + n for n in back}
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert sorted(repeat.downloads) == sorted(
        {10_000 + n for n in range(95, 101)} - repeat.downloaded
    )


def test_a_mark_without_the_oldest_post_is_dropped(repeat):
    # written by an earlier version of this rule
    repeat.cache[incremental.mark_key(MODEL_ID, "Timeline")].pop("oldest", None)
    repeat.areas = ["Timeline"]
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert mark(repeat)["oldest"] == 95


def test_posts_recorded_by_a_labels_only_run_do_not_hide_new_timeline_posts(repeat):
    # a --posts labels run records wall posts 110 and 109 and downloads them;
    # the timeline isn't scanned, so its mark stays at 100
    repeat.recorded["posts"].update({110, 109})
    repeat.downloaded |= {10_110, 10_109}
    repeat.pages["Timeline"] = [
        page(post_dict(110, [10_110]), post_dict(109, [10_109])),
        page(post_dict(108, [10_108]), post_dict(107, [10_107])),
        *timeline_pages(100, 3),
    ]
    repeat.run()
    assert repeat.downloads == [10_108, 10_107]
    assert len(asked(repeat, "Timeline")) == 3


def test_posts_recorded_by_an_interrupted_scan_first_run_are_still_scanned(repeat):
    # a scan-first run wrote post rows 104 to 101 and was stopped before its
    # media rows: nothing is pending, and it never writes the mark
    repeat.recorded["posts"].update({104, 103, 102, 101})
    repeat.pages["Timeline"] = [
        page(post_dict(104, [10_104]), post_dict(103, [10_103])),
        page(post_dict(102, [10_102]), post_dict(101, [10_101])),
        *timeline_pages(100, 3),
    ]
    repeat.run()
    assert repeat.downloads == [10_104, 10_103, 10_102, 10_101]


def test_a_post_that_appears_later_with_an_old_id_is_found_by_the_full_scan(repeat):
    # post 97 was scheduled (or hidden) at the last scan; its id is old
    repeat.pages["Timeline"] = [
        page(post_dict(100, [10_100]), post_dict(99, [10_099])),
        page(post_dict(98, [10_098]), post_dict(97, [10_975])),
        page(post_dict(96, [10_096]), post_dict(95, [10_095])),
    ]
    repeat.run()
    assert 10_975 not in repeat.downloads  # within the full-scan period
    new_run(repeat)
    age_full_scan(repeat, 8)
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert repeat.downloads == [10_975]
    # and that scan is the new full scan
    assert time.time() - mark(repeat)["full_at"] < DAY


def test_force_all_scans_in_full(repeat, settings_stub):
    settings_stub.force_all = True
    repeat.downloaded = set()  # --force-all excludes nothing
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert len(repeat.downloads) == 8


def test_an_area_not_downloaded_from_is_not_marked(harness):
    harness.areas = ["Messages", "Timeline"]
    harness.download_area = {"Timeline"}
    harness.pages["Messages"] = [page(post_dict(60, [20_060], from_user=MODEL_ID))]
    harness.pages["Timeline"] = timeline_pages(100, 1)
    harness.run()
    assert mark(harness, "Messages") is None
    assert mark(harness) is not None


def test_changed_access_means_a_full_scan(repeat):
    ele = SimpleNamespace(
        name=NAME, id=MODEL_ID, active=True,
        model={"fansly": {"subscribed": True, "following": True, "tierId": "5"}},
    )
    repeat.run(ele=ele)
    assert len(asked(repeat, "Timeline")) == 3  # the first run had other access
    new_run(repeat)
    repeat.run(ele=ele)
    assert asked(repeat, "Timeline") == ["Timeline page 1"]
    new_run(repeat)
    ele.model["fansly"]["tierId"] = "6"
    repeat.run(ele=ele)
    assert len(asked(repeat, "Timeline")) == 3


def test_given_after_scans_fully_and_does_not_mark(repeat, settings_stub):
    before = dict(mark(repeat))
    repeat.after = 0
    settings_stub.after = arrow.get(2000, 1, 1)
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert mark(repeat) == before


def test_post_ids_scan_fully_and_do_not_mark(repeat, settings_stub):
    before = dict(mark(repeat))
    settings_stub.post_id = [100]
    repeat.run()
    assert len(asked(repeat, "Timeline")) == 3
    assert mark(repeat) == before


# ------------------------------------------------------------------ the decision on its own


@pytest.fixture
def decision(monkeypatch, settings_stub):
    """early_stop_for with the real switches; a finished full scan with the
    current access is on record."""
    data = {}
    monkeypatch.setattr(incremental, "cache", FakeCache(data))
    monkeypatch.setattr(cache_read, "cache", FakeCache(data))
    settings_stub.incremental_downloads = True
    settings_stub.retry_permanent_skips = False
    ele = SimpleNamespace(name=NAME, id=MODEL_ID, model={"fansly": {"subscribed": True}})
    incremental.record(ele, "Timeline", 10, True, oldest=1)

    async def ids(**k):
        # the database has the mark's posts
        return {1, 2, 10}

    async def pending(model_id, username):
        return set()

    monkeypatch.setattr(incremental, "AREA_IDS", {"Timeline": ids, "Messages": ids})
    monkeypatch.setattr(incremental, "get_posts_missing_media", pending)

    def decide(now=None):
        return asyncio.run(incremental.early_stop_for(ele, "Timeline", now=now))

    return SimpleNamespace(data=data, ele=ele, settings=settings_stub, decide=decide)


def test_with_a_recent_full_scan_and_no_switch_the_scan_may_stop(decision):
    rule = decision.decide()
    assert isinstance(rule, incremental.EarlyStop)
    assert rule.newest == 10


@pytest.mark.parametrize(
    "switch",
    ["after", "incremental off", "full-scan flag", "retry permanent skips", "post id",
     "force all", "no mark", "access changed", "old full scan", "full scans every time"],
)
def test_each_switch_forces_a_full_scan(decision, monkeypatch, switch):
    now = None
    if switch == "after":
        decision.settings.after = arrow.get(2000, 1, 1)
    elif switch == "incremental off":
        decision.settings.incremental_downloads = False
    elif switch == "full-scan flag":
        decision.data[f"{MODEL_ID}_full_timeline_v2_scrape"] = True
    elif switch == "retry permanent skips":
        decision.settings.retry_permanent_skips = True
    elif switch == "post id":
        decision.settings.post_id = [1]
    elif switch == "force all":
        decision.settings.force_all = True
    elif switch == "no mark":
        decision.data.clear()
    elif switch == "access changed":
        decision.ele.model["fansly"]["subscribed"] = False
    elif switch == "old full scan":
        now = time.time() + 7 * DAY + 60
    elif switch == "full scans every time":
        monkeypatch.setattr(incremental, "full_scan_days", lambda: 0)
    assert decision.decide(now=now) is None


def test_within_the_full_scan_period_the_scan_may_stop(decision):
    assert decision.decide(now=time.time() + 7 * DAY - 60) is not None


def test_a_full_scan_dated_in_the_future_means_a_full_scan(decision):
    # the clock was a year ahead when the full scan was recorded
    incremental.record(
        decision.ele, "Timeline", 10, True, now=time.time() + 365 * DAY, oldest=1
    )
    assert decision.decide() is None
    # the full scan this run does is dated now, and the next run may stop
    incremental.record(decision.ele, "Timeline", 10, True, oldest=1)
    assert decision.decide(now=time.time() + 60) is not None


def test_an_early_stopped_scan_keeps_the_last_full_scan_time(decision):
    first = decision.data[incremental.mark_key(MODEL_ID, "Timeline")]
    incremental.record(decision.ele, "Timeline", 12, False, now=first["full_at"] + 3600)
    second = decision.data[incremental.mark_key(MODEL_ID, "Timeline")]
    assert (second["newest"], second["oldest"], second["full_at"]) == (12, 1, first["full_at"])
    assert second["at"] == first["full_at"] + 3600


def test_without_a_full_scan_on_record_an_early_stop_writes_nothing(decision):
    decision.data.clear()
    incremental.record(decision.ele, "Timeline", 12, False)
    assert decision.data == {}


def test_a_scan_that_began_at_before_is_not_a_full_scan(decision):
    first = dict(decision.data[incremental.mark_key(MODEL_ID, "Timeline")])
    decision.settings.before = decision.settings.before_original = arrow.get(2024, 3, 1)
    # it ran to the last page, but from post 6: posts 7 to 10 weren't scanned
    incremental.record(
        decision.ele, "Timeline", 6, True, now=first["full_at"] + 3600, oldest=1
    )
    second = decision.data[incremental.mark_key(MODEL_ID, "Timeline")]
    assert (second["newest"], second["oldest"], second["full_at"]) == (10, 1, first["full_at"])


def test_a_scan_that_began_at_before_writes_no_first_mark(decision):
    decision.data.clear()
    decision.settings.before = decision.settings.before_original = arrow.get(2024, 3, 1)
    incremental.record(decision.ele, "Timeline", 6, True, oldest=1)
    # a mark would let the next run stop at post 6 for good, or count the
    # posts newer than it as scanned
    assert decision.data == {}


@pytest.mark.parametrize("given", ["nothing", "a date ahead"])
def test_a_scan_from_the_newest_post_is_a_full_scan_whatever_before_holds(decision, given):
    # without --before the setting holds a date a few days ahead
    decision.settings.before = arrow.now().shift(days=4)
    decision.settings.before_original = None if given == "nothing" else decision.settings.before
    first = decision.data[incremental.mark_key(MODEL_ID, "Timeline")]
    later = first["full_at"] + 3600
    incremental.record(decision.ele, "Timeline", 12, True, now=later, oldest=1)
    second = decision.data[incremental.mark_key(MODEL_ID, "Timeline")]
    assert (second["newest"], second["full_at"]) == (12, later)


def test_other_areas_never_stop_early(decision):
    assert asyncio.run(incremental.early_stop_for(decision.ele, "Purchased")) is None
    assert asyncio.run(incremental.early_stop_for(decision.ele, "Labels")) is None
    incremental.record(decision.ele, "Purchased", 5, True)
    assert incremental.mark_key(MODEL_ID, "Purchased") not in decision.data


def test_the_page_rule():
    rule = incremental.EarlyStop(newest=6, pending_ids=["2", "99"])
    assert rule.after_page([7, 6]) is False  # 7 is new
    assert rule.after_page([6, 5]) is False  # post 2 still has media, further down
    assert rule.after_page([3, 2]) is True  # down to post 2
    assert rule.after_page([]) is False
    assert incremental.EarlyStop(6, []).after_page([6, 5]) is True
