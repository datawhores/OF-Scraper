"""Fansly downloads each page as it is scanned (sites/fansly/pipeline.py).

Most Fansly links are signed for the address that asked for them, so links
that wait an hour between the scan and the download can be refused. The
pipeline saves each page, selects its media and puts it on a small bounded
queue that download workers take from, so the scan waits while the workers
are behind. These tests run the real producer, selector, queue and workers;
the API pages, database writes and the per-file download are fakes that
record the order of events.
"""

import asyncio
import contextlib
import copy
import logging
import pathlib
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.scraper as scraper
import ofscraper.commands.utils.command as command
import ofscraper.data.api.labels as labels_api
import ofscraper.data.posts.post as post
import ofscraper.db.operations as operations
import ofscraper.db.operations_.profile as profile
import ofscraper.filters.media.filters as filters
import ofscraper.sites.fansly.incremental as incremental
import ofscraper.sites.fansly.pipeline as pipeline
import ofscraper.utils.logs.utils.level as level
import ofscraper.utils.separate as separate
import ofscraper.utils.settings as settings
from ofscraper.classes.of.posts import Post
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.managers.postcollection import PostCollection

from test_fansly_api import (  # noqa: F401  (fansly is a fixture)
    DM_CREATOR,
    DM_CREATOR_ID,
    FakeSession,
    both_routes,
    fansly,
    table_rows,
)

MODEL_ID = 4242
NAME = "a-creator"
BASE = 1_790_000_000
WALL = {"id": "77", "name": "A wall", "type": None}


def media(mid, kind="photo", can_view=True, created=None):
    return {
        "id": mid,
        "type": kind,
        "canView": can_view,
        "createdAt": created,
        "duration": 10 if kind == "video" else None,
        "files": {"full": {"url": f"https://cdn.example/{mid}" if can_view else None}},
    }


def post_dict(pid, media_ids, kinds=None, from_user=None, locked=()):
    created = arrow.get(BASE - pid * 3600).isoformat()
    kinds = kinds or {}
    out = {
        "id": pid,
        "text": f"post {pid}",
        "createdAt": created,
        "postedAt": created,
        "price": 0,
        "isOpened": True,
        "responseType": "post",
        "hashtags": [],
        "media": [
            media(m, kinds.get(m, "photo"), m not in locked, created) for m in media_ids
        ],
    }
    if from_user:
        out["fromUser"] = {"id": from_user}
    return out


def page(*posts):
    return list(posts)


class FakeCache:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, **kwargs):
        self.data[key] = value


# ------------------------------------------------------------------ harness


class Harness:
    """Fakes around the pipeline that record what happens, in order."""

    def __init__(self, monkeypatch, workers=1):
        self.events = []
        self.pages = {area: [] for area in pipeline.ORDER}
        self.gates = {}
        self.on_download = {}
        self.downloads = []
        self.calls = {}
        self.workers = workers
        self.areas = list(pipeline.ORDER)
        self.download_area = set(pipeline.ORDER)
        self.downloaded = set()
        m = monkeypatch

        def area_gen(area):
            async def gen(model_id, username, c=None, post_id=None):
                for number, content in enumerate(self.pages[area], 1):
                    self.events.append(f"{area} page {number}")
                    await asyncio.sleep(0)  # the API call
                    if isinstance(content, Exception):
                        raise content
                    yield copy.deepcopy(content)

            return gen

        m.setattr(
            pipeline,
            "fansly_scrape",
            SimpleNamespace(
                paid_pages=area_gen("Purchased"),
                message_pages=area_gen("Messages"),
                timeline_pages=area_gen("Timeline"),
            ),
        )

        async def labels_data(model_id, c=None):
            return [dict(WALL)] if self.pages["Labels"] else []

        async def known(found, model_id, username):
            return {}

        async def wall_pages(c, label, model_id, known=None, track=False):
            for number, content in enumerate(self.pages["Labels"], 1):
                self.events.append(f"Labels page {number}")
                await asyncio.sleep(0)
                yield label, copy.deepcopy(content)
            self.events.append("wall finished")

        m.setattr(labels_api, "get_labels_data", labels_data)
        m.setattr(labels_api, "get_known_label_posts", known)
        m.setattr(labels_api, "scrape_posts_labels", wall_pages)
        m.setattr(labels_api, "commit_finished_labels", self.record("labels committed"))
        m.setattr(labels_api, "discard_finished_labels", self.record("labels discarded"))

        self.recorded = {"posts": set(), "messages": set()}

        def rows(name):
            async def write(items, model_id=None, username=None, **k):
                self.events.append(f"rows {name}")
                if name in self.recorded:
                    self.recorded[name].update(item.id for item in items)

            return write

        # repeat-run state (incremental.py): the cache and what is recorded
        self.cache = {}
        self.pending = set()
        self.after = None

        def known(name):
            async def ids(model_id=None, username=None):
                return set(self.recorded[name])

            return ids

        async def pending(model_id, username):
            return set(self.pending)

        m.setattr(incremental, "cache", FakeCache(self.cache))
        m.setattr(incremental, "get_after_pre_checks", lambda model_id, area: self.after)
        m.setattr(incremental, "AREA_IDS", {"Timeline": known("posts"), "Messages": known("messages")})
        m.setattr(incremental, "get_posts_missing_media", pending)

        async def table_init(**k):
            self.events.append("table init")

        m.setattr(
            pipeline,
            "operations",
            SimpleNamespace(
                table_init_create=table_init,
                make_post_table_changes=rows("posts"),
                make_messages_table_changes=rows("messages"),
                make_label_table_changes=rows("labels"),
            ),
        )

        async def media_rows(items, **k):
            self.events.append("rows media")

        m.setattr(pipeline, "batch_mediainsert", media_rows)

        async def handle_one(data, task1, total, on_result=None):
            ele = data[1]
            self.events.append(f"download {ele.id}")
            hook = self.on_download.get(ele.id)
            if hook:
                result = await hook(ele)
                if result is not None:
                    return result
            gate = self.gates.get(ele.id)
            if gate:
                await gate.wait()
            self.downloads.append(ele.id)
            return True

        m.setattr(pipeline, "handle_one", handle_one)

        @contextlib.asynccontextmanager
        async def download_session():
            yield "download session"

        m.setattr(
            pipeline,
            "manager",
            SimpleNamespace(
                Manager=SimpleNamespace(
                    session=SimpleNamespace(get_download_session=download_session),
                    stats_manager=SimpleNamespace(
                        update_and_print_stats=self.record("stats")
                    ),
                    current_model_manager=SimpleNamespace(
                        mark_as_processed=self.record("processed")
                    ),
                )
            ),
        )
        noop = lambda *a, **k: None  # noqa: E731
        m.setattr(
            pipeline, "progress_utils",
            SimpleNamespace(setup_live=lambda *a, **k: contextlib.nullcontext()),
        )
        m.setattr(
            pipeline,
            "progress_updater",
            SimpleNamespace(
                activity=SimpleNamespace(update_task=noop),
                download=SimpleNamespace(
                    add_overall_task=lambda *a, **k: 1,
                    update_overall_task=noop,
                    remove_overall_task=noop,
                ),
            ),
        )
        self.m = m
        self.new_pool()
        m.setattr(pipeline, "cache", SimpleNamespace(close=noop))
        m.setattr(pipeline, "setDirectoriesDate", noop)
        m.setattr(pipeline, "get_max_workers", lambda: self.workers)
        m.setattr(pipeline, "get_download_area", lambda: self.download_area)
        m.setattr(pipeline, "after_download_action_script", self.record("after script"))
        m.setattr(pipeline, "set_after_checks", self.record("after check"))
        m.setattr(pipeline, "update_check", self.record("check cache"))

        async def text(posts, username=None):
            self.events.append("text")
            self.calls.setdefault("text", []).append(posts)

        m.setattr(pipeline, "textDownloader", text)

        async def recheck(username, model_id, all_media):
            self.events.append("silent recheck")
            self.calls.setdefault("silent recheck", []).append(
                (username, model_id, [m.id for m in all_media])
            )

        m.setattr(pipeline, "recheck_silent", recheck)
        m.setattr(
            pipeline, "remove_downloads_with_hashes", self.record("duplicate cleanup")
        )

        async def strays(username, model_id, collection):
            self.events.append("strays")
            self.calls.setdefault("strays", []).append(collection)

        m.setattr(post, "clean_stray_media", strays)
        m.setattr(post, "get_final_posts_area", lambda: self.areas)
        m.setattr(filters, "downloaded_media_ids", lambda **k: set(self.downloaded))
        m.setattr(filters, "seperate_self", lambda media: media)
        m.setattr(separate, "seperate_avatars", lambda media: media)
        stop.clear()

    def record(self, name):
        def fn(*args, **kwargs):
            self.events.append(name)
            self.calls.setdefault(name, []).append((args, kwargs))

        return fn

    def new_pool(self):
        """A run shuts the download thread pool down; each run gets its own."""
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.m.setattr(
            pipeline,
            "common_globals",
            SimpleNamespace(mainProcessVariableInit=lambda: None, thread=self.pool),
        )

    def run(self, active=True, ele=None, collection=None):
        ele = ele or SimpleNamespace(name=NAME, id=MODEL_ID, active=active)
        try:
            return asyncio.run(asyncio.wait_for(pipeline.run(ele, None, collection), 10))
        finally:
            self.pool.shutdown(wait=True)
            self.new_pool()

    def index(self, event):
        return self.events.index(event)


@pytest.fixture
def settings_stub(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(
        site="fansly", command="scraper", actions=["download"], users_first=False,
        max_post_count=0, mediasort=None, media_desc=False, text=False,
        text_only=False, post_id=None, after=None, before=None,
        mediatypes=["Images", "Videos", "Audios"], skip_unavailable_content=True,
        system_free_min=0, force_all=False, label=None,
    )
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)
    yield stub
    stop.clear()


@pytest.fixture
def harness(monkeypatch, settings_stub):
    return Harness(monkeypatch)


# ------------------------------------------------------------------ order and freshness


def test_the_first_file_starts_before_the_second_page_is_asked_for(harness):
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101])), page(post_dict(2, [102]))]
    harness.run()
    assert harness.index("download 101") < harness.index("Timeline page 2")
    assert harness.downloads == [101, 102]


def test_the_scan_waits_while_downloads_are_behind(harness):
    """With one worker the queue holds two files. While downloads are blocked
    the scan asks for no more pages than fill the worker and the queue (and
    the one waiting to be queued); each finished download lets it ask for
    the next page."""
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(n, [100 + n])) for n in range(1, 9)]

    def asked():
        return sum(1 for e in harness.events if e.startswith("Timeline page"))

    seen = {}

    async def go():
        harness.gates = {100 + n: asyncio.Event() for n in range(1, 9)}
        ele = SimpleNamespace(name=NAME, id=MODEL_ID, active=True)
        task = asyncio.create_task(pipeline.run(ele, None))
        for _ in range(50):
            await asyncio.sleep(0)
        seen["blocked"] = asked()
        harness.gates[101].set()
        for _ in range(50):
            await asyncio.sleep(0)
        seen["after one"] = asked()
        for gate in harness.gates.values():
            gate.set()
        await asyncio.wait_for(task, 10)

    try:
        asyncio.run(go())
    finally:
        harness.pool.shutdown(wait=True)
    # 1 downloading + 2 queued + 1 waiting to be queued
    assert seen == {"blocked": 4, "after one": 5}
    assert harness.downloads == [100 + n for n in range(1, 9)]


def test_rows_are_saved_before_the_page_is_queued(harness):
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101]))]
    harness.run()
    assert (
        harness.index("rows posts")
        < harness.index("rows media")
        < harness.index("download 101")
    )


def test_areas_run_in_order_one_after_another(harness):
    harness.pages["Purchased"] = [page(post_dict(1, [101]))]
    harness.pages["Messages"] = [page(post_dict(2, [102], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [page(post_dict(3, [103]))]
    harness.pages["Labels"] = [page(post_dict(4, [104]))]
    harness.run()
    pages = [e for e in harness.events if e.endswith("page 1")]
    assert pages == ["Messages page 1", "Labels page 1", "Timeline page 1", "Purchased page 1"]
    assert harness.downloads == [102, 104, 103, 101]


def test_a_media_on_two_pages_or_in_two_areas_downloads_once(harness):
    harness.pages["Messages"] = [page(post_dict(1, [101, 102], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [
        page(post_dict(2, [102, 103])),
        page(post_dict(3, [103, 104])),
    ]
    # a wall holds a timeline post again, and a post of its own
    harness.pages["Labels"] = [page(post_dict(2, [102, 103]), post_dict(5, [104, 105]))]
    harness.run()
    assert sorted(harness.downloads) == [101, 102, 103, 104, 105]
    assert len(harness.downloads) == 5


def test_already_downloaded_media_is_not_queued(harness):
    harness.areas = ["Timeline"]
    harness.downloaded = {102}
    harness.pages["Timeline"] = [page(post_dict(1, [101, 102, 103]))]
    harness.run()
    assert harness.downloads == [101, 103]


def test_an_area_not_downloaded_from_is_saved_but_not_queued(harness):
    harness.areas = ["Messages", "Timeline"]
    harness.download_area = {"Timeline"}
    harness.pages["Messages"] = [page(post_dict(1, [101], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [page(post_dict(2, [102]))]
    harness.run()
    assert "rows messages" in harness.events
    assert harness.downloads == [102]


# ------------------------------------------------------------------ failures


def test_an_area_that_fails_part_way_keeps_its_pages_and_the_next_area_runs(
    harness, caplog
):
    level.addtraceback()
    harness.areas = ["Messages", "Timeline", "Purchased"]
    harness.pages["Messages"] = [page(post_dict(1, [101], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [
        page(post_dict(2, [102])),
        page(post_dict(3, [103])),
        ValueError("boom"),
    ]
    harness.pages["Purchased"] = [page(post_dict(4, [104]))]
    with caplog.at_level(logging.WARNING, logger="shared"):
        harness.run()
    assert harness.downloads == [101, 102, 103, 104]
    assert f"[{NAME}] Timeline failed: ValueError: boom" in caplog.messages
    # only the area that reached its end is recorded as scanned
    checked = [args for args, _ in harness.calls["after check"]]
    assert checked == [(MODEL_ID, "Messages")]


def test_a_failed_area_is_not_recorded_but_finished_ones_are(harness):
    harness.areas = ["Messages", "Timeline"]
    harness.pages["Messages"] = [page(post_dict(1, [101], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [page(post_dict(2, [102]))]
    harness.run()
    checked = [args for args, _ in harness.calls["after check"]]
    assert checked == [(MODEL_ID, "Messages"), (MODEL_ID, "Timeline")]


# ------------------------------------------------------------------ end of creator


def test_end_of_creator_steps_run_once_with_everything(harness, settings_stub):
    settings_stub.text = True
    harness.pages["Messages"] = [page(post_dict(1, [101], from_user=MODEL_ID))]
    harness.pages["Timeline"] = [page(post_dict(2, [102, 103])), page(post_dict(3, [104]))]
    harness.pages["Labels"] = [page(post_dict(5, [105]))]
    harness.run()
    stats = harness.calls["stats"]
    assert len(stats) == 1
    username, action, media_ = stats[0][0]
    assert (username, action) == (NAME, "download")
    assert [m.id for m in media_] == [101, 105, 102, 103, 104]
    script = harness.calls["after script"]
    assert len(script) == 1
    args, kwargs = script[0]
    assert [m.id for m in args[1]] == [101, 105, 102, 103, 104]
    assert sorted(p.id for p in args[2]) == [1, 2, 3, 5]
    assert kwargs == {"action": "download"}
    assert len(harness.calls["processed"]) == 1
    # one text download, for every post of the run
    assert [sorted(p.id for p in posts) for posts in harness.calls["text"]] == [[1, 2, 3, 5]]
    # duplicate files are removed once the creator's downloads are done (#609)
    assert harness.calls["duplicate cleanup"] == [((NAME, MODEL_ID), {})]
    assert harness.index("duplicate cleanup") > harness.index("silent recheck")
    # stray cleanup sees every post scanned
    (collection,) = harness.calls["strays"]
    assert sorted(p.id for p in collection.posts) == [1, 2, 3, 5]
    # labels are committed once their rows and media rows are saved
    assert harness.index("rows labels") < harness.index("labels committed")
    last_media_rows = len(harness.events) - 1 - harness.events[::-1].index("rows media")
    assert last_media_rows < harness.index("labels committed")
    assert harness.index("check cache") > harness.index("rows labels")


# ------------------------------------------------------------------ stopping


def test_a_stop_ends_the_scan_and_leaves_queued_files_unstarted(harness):
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(n, [100 + n])) for n in range(1, 9)]

    async def stop_now(ele):
        for _ in range(20):  # the scan fills the queue meanwhile
            await asyncio.sleep(0)
        stop.request()
        return None

    harness.on_download[101] = stop_now
    queued = {}
    real_take = pipeline._take_page

    async def take(run, area, posts, download, number):
        await real_take(run, area, posts, download, number)
        queued["media"] = list(run.media)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(pipeline, "_take_page", take)
        with pytest.raises(stop.DownloadsStopped):
            harness.run()
    asked = sum(1 for e in harness.events if e.startswith("Timeline page"))
    assert asked < 8
    assert harness.downloads == [101]
    untaken = [m for m in queued["media"] if m.id != 101]
    assert untaken and all(m.download_unstarted for m in untaken)
    # stats still print; the creator isn't marked done; nothing is recorded
    assert len(harness.calls["stats"]) == 1
    assert "processed" not in harness.calls
    assert "after check" not in harness.calls
    assert "labels committed" not in harness.calls
    assert "duplicate cleanup" not in harness.calls


def test_a_stop_during_a_stream_does_not_wait_for_the_video(harness, monkeypatch):
    harness.workers = 2
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101, 102]))]
    monkeypatch.setattr(pipeline.fansly_video, "uses_stream", lambda ele: ele.id == 101)

    async def stream(ele):
        # the stream downloader takes no part in the stop module; like
        # handle_one, a cancel under a stop leaves an unstarted item
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            if not stop.requested.is_set():
                raise
            ele.download_unstarted = True
            return False

    async def stop_now(ele):
        await asyncio.sleep(0.05)
        stop.request()
        return None

    harness.on_download[101] = stream
    harness.on_download[102] = stop_now
    with pytest.raises(stop.DownloadsStopped):
        harness.run()
    assert harness.downloads == [102]
    stats = harness.calls["stats"][0][0][2]
    video = next(m for m in stats if m.id == 101)
    assert video.download_unstarted is True


@pytest.mark.parametrize(
    "site, downloading, message",
    [
        ("fansly", False, "Stopping the fetch. A second Ctrl+C quits."),
        ("fansly", True,
         "Stopping downloads; Part files are kept for Resume. A second Ctrl+C quits."),
        # OnlyFans keeps the message it had
        ("onlyfans", True, "Stopping the fetch. A second Ctrl+C quits."),
    ],
)
def test_ctrl_c_while_scanning_and_downloading_says_downloads_stop(
    settings_stub, caplog, site, downloading, message
):
    settings_stub.site = site

    async def go():
        @stop.fetching
        async def fetch():
            await asyncio.sleep(10)

        async def transfer():
            item = SimpleNamespace()
            with stop.transfer(item):
                stop.started(item)
                await asyncio.sleep(10)

        tasks = [asyncio.create_task(fetch())]
        if downloading:
            tasks.append(asyncio.create_task(transfer()))
        await asyncio.sleep(0.01)
        stop.handle_interrupt(None, None)
        await asyncio.gather(*tasks, return_exceptions=True)

    with caplog.at_level(logging.WARNING, logger="shared"):
        asyncio.run(go())
    assert caplog.messages == [message]


# ------------------------------------------------------------------ which runs, which areas


@pytest.mark.parametrize(
    "change, expected",
    [
        ({}, True),
        ({"site": "onlyfans"}, False),
        ({"command": "metadata"}, False),
        ({"actions": ["like"]}, False),
        ({"actions": ["download", "like"]}, False),
        ({"users_first": True}, False),
        ({"text_only": True}, False),
        # these need the whole list first, then download through the pipeline
        ({"max_post_count": 10}, True),
        ({"mediasort": "date"}, True),
        ({"media_desc": True}, True),
    ],
)
def test_applies_only_to_plain_fansly_downloads(settings_stub, change, expected):
    for key, value in change.items():
        setattr(settings_stub, key, value)
    assert pipeline.applies() is expected


@pytest.mark.parametrize(
    "change, expected",
    [
        ({}, False),
        ({"max_post_count": 10}, True),
        ({"mediasort": "date"}, True),
        ({"media_desc": True}, True),
    ],
)
def test_runs_that_need_the_whole_list_are_ordered(settings_stub, change, expected):
    for key, value in change.items():
        setattr(settings_stub, key, value)
    assert pipeline.ordered() is expected


def test_the_scraper_hands_a_creator_to_the_pipeline_only_when_it_applies(monkeypatch):
    calls = []

    async def pipeline_run(ele, c, collection=None):
        calls.append(("pipeline", ele.name, c, collection))

    async def scan(ele, c=None):
        calls.append(("scan", ele.name, c))
        return "posts"

    async def action(ele=None, postcollection=None):
        calls.append(("action", ele.name, postcollection))

    monkeypatch.setattr(pipeline, "run", pipeline_run)
    monkeypatch.setattr(command, "post_media_process", scan)
    monkeypatch.setattr(scraper, "post_media_process", scan)
    monkeypatch.setattr(command.CommandManager, "_data_helper", lambda *a: None)
    monkeypatch.setattr(command.CommandManager, "_avatar_helper", lambda *a: None)
    manager = scraper.scraperManager()
    ele = SimpleNamespace(name="a")
    for applies, ordered in ((True, False), (True, True), (False, False)):
        monkeypatch.setattr(pipeline, "applies", lambda applies=applies: applies)
        monkeypatch.setattr(pipeline, "ordered", lambda ordered=ordered: ordered)
        asyncio.run(manager._process_user(ele, "c", action))
    assert calls == [
        ("pipeline", "a", "c", None),
        # a whole-list run scans first and hands the pipeline the result
        ("scan", "a", "c"),
        ("pipeline", "a", "c", "posts"),
        ("scan", "a", "c"),
        ("action", "a", "posts"),
    ]


@pytest.mark.parametrize("active", [True, False])
@pytest.mark.parametrize("skip", [True, False])
def test_the_pipeline_scans_the_areas_the_scan_first_path_would(
    harness, settings_stub, monkeypatch, caplog, active, skip
):
    settings_stub.skip_unavailable_content = skip
    harness.areas = ["Timeline", "Archived", "Messages", "Purchased", "Labels", "Pinned"]
    ele = SimpleNamespace(name=NAME, id=MODEL_ID, active=active)

    scanned = []

    def fake(area):
        async def process(*args, **kwargs):
            scanned.append(area)

        return process

    for name, area in [
        ("process_paid_post", "Purchased"),
        ("process_messages", "Messages"),
        ("process_timeline_posts", "Timeline"),
        ("process_labels", "Labels"),
        ("process_pinned_posts", "Pinned"),
        ("process_archived_posts", "Archived"),
    ]:
        monkeypatch.setattr(post, name, fake(area))
    monkeypatch.setattr(post, "get_like_area", lambda: [])
    monkeypatch.setattr(post, "get_download_area", lambda: set(harness.areas))
    monkeypatch.setattr(
        post, "progress_utils",
        SimpleNamespace(setup_live=lambda *a, **k: contextlib.nullcontext()),
    )
    with caplog.at_level(logging.INFO, logger="shared"):
        asyncio.run(post.process_tasks(MODEL_ID, NAME, ele))
        scan_first_lines = list(caplog.messages)
        caplog.clear()
        areas = pipeline.areas_for(ele, NAME)
        pipeline_lines = [m for m in caplog.messages]
    assert set(areas) == set(scanned)
    assert areas == [a for a in pipeline.ORDER if a in scanned]
    assert pipeline_lines == [m for m in scan_first_lines if "skipping" in m.lower()]


# ------------------------------------------------------------------ same files, same folders


def purchase_dict(media_id, hours_ago):
    """A purchase: Fansly's purchases become Paid posts dated when bought."""
    created = arrow.get(BASE - hours_ago * 3600).isoformat()
    out = post_dict(media_id, [media_id])
    out.update({"createdAt": created, "postedAt": created, "text": "",
                "responseType": "purchased"})
    for item in out["media"]:
        item["createdAt"] = created
    return out


RESPONSE_TYPES = {"Timeline": "Timeline", "Purchased": "Paid"}


def build(area, posts):
    return [
        Post(copy.deepcopy(p), MODEL_ID, NAME, RESPONSE_TYPES.get(area)) for p in posts
    ]


def equivalence_pages():
    """Pages in the pipeline's order, with repeats, types, dates, a locked
    item and bought files."""
    kinds = {201: "video", 203: "audio", 205: "video", 212: "video"}
    return [
        ("Messages", [
            post_dict(1, [201, 202], kinds, from_user=MODEL_ID),
            post_dict(2, [203], kinds, from_user=999),  # sent by the account
        ]),
        ("Timeline", [post_dict(10, [204, 205, 202], kinds), post_dict(30, [206], kinds)]),
        ("Timeline", [post_dict(60, [207, 208], kinds, locked=(208,)), post_dict(90, [209])]),
        ("Timeline", [post_dict(120, [210, 204]), post_dict(150, [211, 212], kinds)]),
        # 201 bought in a message, 230 bought and found nowhere else
        ("Purchased", [purchase_dict(201, 0.5), purchase_dict(230, 0.25)]),
    ]


# Files the pipeline files under another post than the scan-first path,
# which keeps the oldest copy: the pipeline keeps the first copy it sees.
DIFFERENT_POST = {
    202,  # in a message and in an older timeline post: filed with the message
    204,  # in two timeline posts: filed under the newer one, seen first
}


@pytest.fixture
def saved_paths(monkeypatch, tmp_path):
    """Where each media is saved, with a layout that shows the area, the
    post and the label."""
    quiet = SimpleNamespace(
        **{name: (lambda *a, **k: None) for name in ("trace", "debug", "info", "warning", "error")}
    )

    async def no_script(*a, **k):
        return None

    m = monkeypatch
    m.setattr(placeholder, "log", quiet)
    m.setattr(placeholder, "naming_script", no_script)
    m.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    m.setattr(placeholder.me, "get_id", lambda: 1)
    m.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    m.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    m.setattr(placeholder.common_paths, "get_save_location", lambda *a, **k: str(tmp_path / "data"))
    m.setattr(placeholder.config_file, "open_config", lambda: {})
    m.setattr(placeholder.settings, "get_args", lambda: SimpleNamespace())
    m.setattr(
        placeholder.manager, "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(get_model=lambda _u: None)),
    )
    m.setattr(placeholder.data, "get_date", lambda *a, **k: "YYYY-MM-DD")
    m.setattr(placeholder.data, "get_dirformat",
              lambda *a, **k: "{model_username}/{responsetype}/{label}/{mediatype}")
    m.setattr(placeholder.data, "get_fileformat", lambda *a, **k: "{date}_{post_id}_{media_id}.{ext}")
    root = tmp_path / "data"

    def where(items):
        async def go():
            out = {}
            for item in items:
                names = await placeholder.Placeholders(item, "bin").init()
                out[item.id] = (item.post_id, pathlib.Path(names.filepath).relative_to(root).as_posix())
            return out

        return asyncio.run(go())

    return where


def full_list_media(pages):
    collection = PostCollection(model_id=MODEL_ID, username=NAME)
    for area, posts in pages:
        collection.add_posts(build(area, posts), actions=["download"])
    return collection.get_media_to_download()


def pipeline_media(monkeypatch, pages):
    async def no_rows(*a, **k):
        pass

    monkeypatch.setattr(pipeline, "batch_mediainsert", no_rows)
    run = pipeline._Run(SimpleNamespace(name=NAME, id=MODEL_ID), None)

    async def go():
        run.queue = asyncio.Queue()
        run.selector = pipeline.Selector(MODEL_ID, NAME)
        # the areas in the pipeline's own order, whatever order they come in
        ordered = sorted(pages, key=lambda p: pipeline.ORDER.index(p[0]))
        for number, (area, posts) in enumerate(ordered, 1):
            await pipeline._take_page(run, area, build(area, posts), True, number)

    asyncio.run(go())
    ids = [m.id for m in run.media]
    assert len(ids) == len(set(ids))
    return run.media


def no_progress(monkeypatch):
    noop = lambda *a, **k: None  # noqa: E731
    monkeypatch.setattr(
        pipeline, "progress_updater",
        SimpleNamespace(
            activity=SimpleNamespace(update_task=noop),
            download=SimpleNamespace(update_overall_task=noop),
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"mediatypes": ["Videos"]},
        {"mediatypes": ["Images", "Audios"]},
        {"after": arrow.get(BASE - 100 * 3600), "before": arrow.get(BASE - 20 * 3600)},
        {"force_all": True},
        {"downloaded": {202, 207, 211}},
        {"downloaded": {202, 207, 211}, "force_all": True},
    ],
    ids=["default", "videos", "images-audios", "dates", "force-all", "downloaded",
         "downloaded-force-all"],
)
def test_the_pipeline_saves_the_files_the_full_list_saves_in_the_same_places(
    settings_stub, monkeypatch, saved_paths, change
):
    change = dict(change)
    downloaded = change.pop("downloaded", set())
    for key, value in change.items():
        setattr(settings_stub, key, value)
    no_progress(monkeypatch)
    monkeypatch.setattr(filters, "get_media_ids_downloaded", lambda **k: set(downloaded))
    monkeypatch.setattr(filters, "get_media_ids_downloaded_model_sync", lambda **k: set(downloaded))
    monkeypatch.setattr(separate, "seperate_avatars", lambda media: media)
    monkeypatch.setattr(filters.me_util, "get_id", lambda: 999)
    pages = equivalence_pages()
    expected = saved_paths(full_list_media(pages))
    assert expected  # the case selects something
    got = saved_paths(pipeline_media(monkeypatch, pages))
    assert set(got) == set(expected)
    differ = {i for i in expected if got[i] != expected[i]}
    assert differ <= DIFFERENT_POST


def test_a_bought_file_is_saved_with_its_message_not_in_paid(
    settings_stub, monkeypatch, saved_paths
):
    no_progress(monkeypatch)
    monkeypatch.setattr(filters, "get_media_ids_downloaded", lambda **k: set())
    monkeypatch.setattr(filters, "get_media_ids_downloaded_model_sync", lambda **k: set())
    monkeypatch.setattr(separate, "seperate_avatars", lambda media: media)
    monkeypatch.setattr(filters.me_util, "get_id", lambda: 999)
    # the purchase listed first: only the pipeline's area order puts it last
    pages = sorted(equivalence_pages(), key=lambda a: a[0] != "Purchased")
    assert pages[0][0] == "Purchased"
    expected = saved_paths(full_list_media(pages))
    got = saved_paths(pipeline_media(monkeypatch, pages))
    # filed under its message, as the scan-first path files it
    assert got[201][0] == 1
    assert got[201] == expected[201]
    # bought and found nowhere else: filed as a purchase, as before
    assert got[230][0] == 230
    assert got[230] == expected[230]


def test_a_wall_post_also_on_the_timeline_keeps_its_label(harness, saved_paths):
    downloaded = []

    async def hook(ele):
        downloaded.append(ele)

    harness.on_download = {102: hook}
    harness.areas = ["Timeline", "Labels"]
    harness.pages["Timeline"] = [page(post_dict(2, [102]))]
    harness.pages["Labels"] = [page(post_dict(2, [102]))]
    harness.run()
    (ele,) = downloaded
    assert f"/{WALL['name']}/" in saved_paths([ele])[102][1]


def test_the_scan_stops_with_the_error_when_every_worker_has_ended(harness):
    async def die(ele):
        raise RuntimeError("worker broke")

    harness.workers = 1
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(n, [100 + n])) for n in range(1, 9)]
    # an error that escapes handle_one ends the worker
    harness.on_download = {101: die}
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run()
    asked = sum(1 for e in harness.events if e.startswith("Timeline page"))
    assert asked < 8


def test_files_left_queued_when_every_worker_has_ended_fail_the_run(harness):
    async def die(ele):
        raise RuntimeError("worker broke")

    harness.workers = 1
    harness.areas = ["Timeline"]
    # one page that fits the queue: the scan never has to wait for room
    harness.pages["Timeline"] = [page(post_dict(1, [101]), post_dict(2, [102]))]
    harness.on_download = {101: die}
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run()
    assert harness.downloads == []
    assert "processed" not in harness.events


def test_a_worker_that_ends_on_the_last_file_fails_the_run(harness):
    async def die(ele):
        raise RuntimeError("worker broke")

    harness.workers = 1
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101]), post_dict(2, [102]))]
    # nothing is left in the queue when the only worker ends
    harness.on_download = {102: die}
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run()
    assert harness.downloads == [101]
    assert "processed" not in harness.events


def test_one_worker_ending_while_the_others_finish_fails_the_run(harness):
    async def die(ele):
        raise RuntimeError("worker broke")

    harness.workers = 2
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(*(post_dict(n, [100 + n]) for n in range(1, 5)))]
    harness.on_download = {101: die}
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run()
    # the other worker downloaded the rest before the run failed
    assert sorted(harness.downloads) == [102, 103, 104]
    assert "processed" not in harness.events


def test_a_worker_cancelled_without_a_stop_fails_the_run(harness):
    async def cancelled(ele):
        raise asyncio.CancelledError()

    harness.workers = 1
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101]), post_dict(2, [102]))]
    # nobody asked for a stop, and nothing is left queued when the worker ends
    harness.on_download = {102: cancelled}
    with pytest.raises(RuntimeError, match="a download worker was cancelled"):
        harness.run()
    assert harness.downloads == [101]
    assert "processed" not in harness.events


def test_the_first_worker_to_fail_gives_the_run_its_error(harness):
    async def late(ele):
        await asyncio.sleep(0.05)
        raise RuntimeError("failed second")

    async def early(ele):
        raise RuntimeError("failed first")

    harness.workers = 2
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101]), post_dict(2, [102]))]
    # the worker started first takes 101 and fails last
    harness.on_download = {101: late, 102: early}
    with pytest.raises(RuntimeError, match="failed first"):
        harness.run()


def test_workers_that_fail_in_the_same_step_are_taken_in_the_order_they_failed(
    harness, monkeypatch
):
    gate = asyncio.Event()

    async def second(ele):
        # the worker started first: it comes to wait after the other one
        for _ in range(3):
            await asyncio.sleep(0)
        await gate.wait()
        raise RuntimeError("failed second")

    async def first(ele):
        await gate.wait()
        raise RuntimeError("failed first")

    real_take = pipeline._take_page

    async def take(run, area, posts, download, number):
        if number == 2:
            # the scan wakes in the same step as both workers, after them,
            # and finds every worker ended
            asyncio.get_running_loop().call_later(0.05, gate.set)
            for _ in range(6):
                await asyncio.sleep(0)
            await gate.wait()
        await real_take(run, area, posts, download, number)

    monkeypatch.setattr(pipeline, "_take_page", take)
    harness.workers = 2
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [
        page(post_dict(1, [101]), post_dict(2, [102])), page(post_dict(3, [103])),
    ]
    harness.on_download = {101: second, 102: first}
    with pytest.raises(RuntimeError, match="failed first"):
        harness.run()


class Log:
    """Keeps what is logged, by level."""

    def __init__(self):
        self.said = {}

    def __getattr__(self, name):
        return self.said.setdefault(name, []).append


def test_a_worker_error_is_still_said_when_a_stop_follows_it(harness, monkeypatch):
    async def die(ele):
        raise RuntimeError("worker broke")

    async def stop_now(ele):
        await asyncio.sleep(0.05)
        stop.request()
        return None

    log = Log()
    monkeypatch.setattr(pipeline, "log", log)
    harness.workers = 2
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101]), post_dict(2, [102]))]
    harness.on_download = {101: die, 102: stop_now}
    with pytest.raises(stop.DownloadsStopped):
        harness.run()
    # said once, and where it was raised is kept for the log file
    assert len([line for line in log.said["warning"] if "worker broke" in line]) == 1
    (trace,) = log.said["traceback_"]
    assert "Traceback" in trace and "in die" in trace and "worker broke" in trace


def test_a_stop_whose_cancel_reaches_an_idle_worker_is_not_said_as_an_error(
    harness, monkeypatch
):
    async def stop_now(ele):
        stop.request()
        # the stop's cancel of this transfer arrives after the transfer is
        # over, while the worker waits for its next file
        asyncio.get_running_loop().call_later(0.05, asyncio.current_task().cancel)
        return None

    log = Log()
    monkeypatch.setattr(pipeline, "log", log)
    monkeypatch.setattr(pipeline, "QUEUE_PER_WORKER", 8)
    harness.workers = 1
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101]))]
    harness.on_download = {101: stop_now}
    real_drain = pipeline._drain

    async def drain(run, workers):
        # the cancel lands before the worker is told to end
        await asyncio.sleep(0.2)
        await real_drain(run, workers)

    monkeypatch.setattr(pipeline, "_drain", drain)
    with pytest.raises(stop.DownloadsStopped):
        harness.run()
    assert not [line for line in log.said.get("warning", []) if "ended on an error" in line]


def test_a_failed_run_does_not_keep_its_walls_as_finished(harness):
    async def die(ele):
        raise RuntimeError("worker broke")

    harness.workers = 1
    harness.areas = ["Labels"]
    harness.pages["Labels"] = [page(post_dict(1, [101]), post_dict(2, [102]))]
    harness.on_download = {101: die}
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run()
    assert "wall finished" in harness.events
    assert "labels discarded" in harness.events
    assert "labels committed" not in harness.events


# ------------------------------------------------------------------ database rows


def rows_without_ids(db):
    """Every table's rows without the row id, which only shows insert order."""
    return {
        name: sorted((row[1:] for row in rows), key=repr)
        for name, rows in table_rows(db).items()
    }


@pytest.fixture
def two_dbs(monkeypatch, tmp_path):
    current = {"db": tmp_path / "scan_first.db"}
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, mid, name: current["db"],
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    # one moment for both runs: the dates a name was seen on are the time of
    # the run, and the two databases are compared row for row
    seen = arrow.get("2026-01-01T00:00:00+00:00")
    monkeypatch.setattr(profile, "_now", lambda: seen)
    return current


def test_the_database_rows_match_the_scan_first_path(fansly, two_dbs, tmp_path, monkeypatch):
    monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: set())
    monkeypatch.setattr(filters, "seperate_self", lambda media: media)
    monkeypatch.setattr(separate, "seperate_avatars", lambda media: media)
    monkeypatch.setattr(incremental, "cache", FakeCache({}))
    no_progress(monkeypatch)

    async def scan_first():
        c = FakeSession(both_routes)
        await operations.table_init_create(model_id=DM_CREATOR_ID, username=DM_CREATOR)
        collection = PostCollection(model_id=DM_CREATOR_ID, username=DM_CREATOR)
        for area in (post.process_messages, post.process_timeline_posts):
            posts, _ = await area(DM_CREATOR_ID, DM_CREATOR, c)
            collection.add_posts(posts, actions=["download"])
        await batch_mediainsert(
            collection.all_unique_media,
            model_id=DM_CREATOR_ID,
            username=DM_CREATOR,
            downloaded=False,
        )

    async def by_page():
        run = pipeline._Run(SimpleNamespace(name=DM_CREATOR, id=DM_CREATOR_ID), FakeSession(both_routes))
        run.queue = asyncio.Queue()
        run.selector = pipeline.Selector(DM_CREATOR_ID, DM_CREATOR)
        await operations.table_init_create(model_id=DM_CREATOR_ID, username=DM_CREATOR)
        for area in ("Messages", "Timeline"):
            await pipeline._scan_area(run, area, True)
        await pipeline._write_locked_rows(run)
        assert run.media  # pages were queued

    asyncio.run(scan_first())
    first = rows_without_ids(two_dbs["db"])
    two_dbs["db"] = tmp_path / "by_page.db"
    asyncio.run(by_page())
    second = rows_without_ids(two_dbs["db"])
    assert first["posts"] and first["messages"] and first["medias"]
    assert second == first


def fake_areas(monkeypatch):
    """Every area of one creator, with files in two areas: a bought message
    file, a wall post that is also on the timeline, and a file locked in a
    newer post and open in an older one."""
    message = post_dict(1, [201, 202], from_user=MODEL_ID)
    message["responseType"] = "message"
    timeline = [
        [post_dict(20, [205]), post_dict(30, [206, 207, 208], locked=(207, 208))],
        [post_dict(40, [207, 209])],
    ]
    wall = [post_dict(20, [205])]
    bought = [purchase_dict(201, 0.5), purchase_dict(230, 0.25)]

    def pages_of(content):
        async def gen(*a, **k):
            for one in content:
                yield copy.deepcopy(one)

        return gen

    def all_of(content):
        async def get(*a, **k):
            return [copy.deepcopy(x) for one in content for x in one]

        return get

    async def label_names(c, model_id):
        yield [dict(WALL)]

    async def label_pages(c, label, model_id):
        yield copy.deepcopy(wall)

    scrape = pipeline.fansly_scrape
    m = monkeypatch
    m.setattr(scrape, "message_pages", pages_of([[message]]))
    m.setattr(scrape, "get_messages", all_of([[message]]))
    m.setattr(scrape, "timeline_pages", pages_of(timeline))
    m.setattr(scrape, "get_timeline_posts", all_of(timeline))
    m.setattr(scrape, "paid_pages", pages_of([bought]))
    m.setattr(scrape, "get_paid_posts", all_of([bought]))
    m.setattr(scrape, "label_names", label_names)
    m.setattr(scrape, "label_pages", label_pages)


def test_every_table_matches_the_scan_first_path_with_files_in_two_areas(
    settings_stub, two_dbs, tmp_path, monkeypatch
):
    areas = ["Messages", "Timeline", "Purchased", "Labels"]
    fake_areas(monkeypatch)
    monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: set())
    monkeypatch.setattr(filters, "get_media_ids_downloaded", lambda **k: set())
    monkeypatch.setattr(filters, "get_media_ids_downloaded_model_sync", lambda **k: set())
    monkeypatch.setattr(filters, "seperate_self", lambda media: media)
    monkeypatch.setattr(separate, "seperate_avatars", lambda media: media)
    monkeypatch.setattr(labels_api, "update_check", lambda *a, **k: None)
    monkeypatch.setattr(labels_api, "get_known_label_posts", _no_known)
    monkeypatch.setattr(
        labels_api, "cache",
        SimpleNamespace(get=lambda key, default=None, **k: default, set=lambda *a, **k: None),
    )
    monkeypatch.setattr(post, "set_after_checks", lambda *a, **k: None)
    monkeypatch.setattr(post, "get_final_posts_area", lambda: list(areas))
    monkeypatch.setattr(post, "get_like_area", lambda: set())
    monkeypatch.setattr(post, "get_download_area", lambda: set(areas))
    monkeypatch.setattr(pipeline, "get_download_area", lambda: set(areas))
    monkeypatch.setattr(
        post, "progress_utils",
        SimpleNamespace(setup_live=lambda *a, **k: contextlib.nullcontext()),
    )
    no_progress(monkeypatch)
    monkeypatch.setattr(incremental, "cache", FakeCache({}))
    ele = SimpleNamespace(name=NAME, id=MODEL_ID, active=True)

    async def scan_first():
        await operations.table_init_create(model_id=MODEL_ID, username=NAME)
        collection = await post.process_tasks(MODEL_ID, NAME, ele)
        await batch_mediainsert(
            collection.all_unique_media, model_id=MODEL_ID, username=NAME, downloaded=False
        )

    async def by_page():
        await operations.table_init_create(model_id=MODEL_ID, username=NAME)
        run = pipeline._Run(ele, None)
        run.queue = asyncio.Queue()
        run.selector = pipeline.Selector(MODEL_ID, NAME)
        await pipeline._produce(run)
        assert run.media

    labels_api._finished_labels.clear()
    asyncio.run(scan_first())
    first = rows_without_ids(two_dbs["db"])
    labels_api._finished_labels.clear()
    two_dbs["db"] = tmp_path / "by_page.db"
    asyncio.run(by_page())
    second = rows_without_ids(two_dbs["db"])
    labels_api._finished_labels.clear()
    for table in ("medias", "posts", "messages", "labels"):
        assert first[table], table
        assert second[table] == first[table], table
    # one row per file
    media_ids = [row[0] for row in second["medias"]]
    assert len(media_ids) == len(set(media_ids))


async def _no_known(found, model_id, username):
    return {}


def test_media_the_filters_leave_out_is_reported_once(harness, settings_stub, caplog):
    # page by page, the run never builds the full list; it still says once,
    # at the end, what the filters left out and by which setting
    settings_stub.mediatypes = ["Images"]
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [
        page(post_dict(1, [101, 102], kinds={102: "video"})),
        page(post_dict(2, [103], kinds={103: "video"})),
    ]
    with caplog.at_level("INFO"):
        harness.run()
    assert harness.downloads == [101]
    assert [r.getMessage() for r in caplog.records if "media left out" in r.getMessage()] == [
        f"[{NAME}] 2 media left out: 2 by --mediatype or download_options.filter"
    ]


def test_media_already_downloaded_is_reported_once(harness, caplog):
    # page by page, media the database marks as downloaded is counted too
    harness.areas = ["Timeline"]
    harness.downloaded = {101, 103}
    harness.pages["Timeline"] = [
        page(post_dict(1, [101, 102])),
        page(post_dict(2, [103])),
    ]
    with caplog.at_level("INFO"):
        harness.run()
    assert harness.downloads == [102]
    assert [r.getMessage() for r in caplog.records if "media left out" in r.getMessage()] == [
        f"[{NAME}] 2 media left out: 2 already downloaded"
        " (--force-all downloads them again, or manual --url for one post)"
    ]
