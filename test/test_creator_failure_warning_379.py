"""A creator's failure shows at normal output, and the run goes on (#379).

The command loops used to log a creator's error only at traceback level, so
at the normal --output level nothing said a creator had failed. That's how
the metadata crash in #376 went unnoticed.

Each test runs the real command loop with two creators, the first of which
fails, or the real daemon loop with a failing pass, and watches the "shared"
logger through handlers set to the levels the console uses. Ctrl+C still
stops every loop at once.
"""

import asyncio
import contextlib
import logging
import queue
import threading
import time
from types import SimpleNamespace

import pytest

import ofscraper.commands.scraper.scraper as scraper
import ofscraper.commands.scraper.utils.schedule as daemon_schedule
import ofscraper.commands.utils.command as command
import ofscraper.data.posts.post as post
import ofscraper.utils.logs.utils.level as level


class Collect(logging.Handler):
    def __init__(self, level_):
        super().__init__(level_)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def messages(self):
        return [r.getMessage() for r in self.records]


class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def reset_sleep(self):
        pass


def creator(name):
    return SimpleNamespace(name=name, id=hash(name) % 1000, avatar=None)


@pytest.fixture
def logs(monkeypatch):
    level.addtraceback()
    log = logging.getLogger("shared")
    normal = Collect(level.getNumber("NORMAL"))
    traces = Collect(logging.TRACEBACK_)
    old_level = log.level
    log.setLevel(1)
    log.addHandler(normal)
    log.addHandler(traces)
    # the progress bars and per-creator banner aren't what's tested here
    monkeypatch.setattr(command.CommandManager, "_data_helper", lambda *_: None)
    monkeypatch.setattr(command.CommandManager, "_avatar_helper", lambda *_: None)
    for name in ("update_user", "update_overall", "update_task"):
        monkeypatch.setattr(command.progress_updater.activity, name, lambda **_: None)
    yield SimpleNamespace(normal=normal, traces=traces)
    log.removeHandler(normal)
    log.removeHandler(traces)
    log.setLevel(old_level)


def fail_first(done):
    async def action(ele=None, **_):
        if ele.name == "first":
            raise ValueError("boom")
        done.append(ele.name)

    return action


def check_failure_shown(logs, what=""):
    warnings = [
        r.getMessage()
        for r in logs.normal.records
        if r.levelno == logging.WARNING
    ]
    assert warnings == [f"[first]{what} failed: ValueError: boom"]
    # the full traceback stays at traceback level only
    tracebacks = [
        r.getMessage() for r in logs.traces.records if r.levelno == logging.TRACEBACK_
    ]
    assert any("Traceback" in t and "boom" in t for t in tracebacks)
    assert not any("Traceback" in m for m in logs.normal.messages())


def test_normal_loop_warns_and_goes_on(logs, monkeypatch):
    async def posts(ele, c=None):
        return SimpleNamespace()

    monkeypatch.setattr(command, "post_media_process", posts)
    done = []
    users = [creator("first"), creator("second")]
    asyncio.run(
        command.CommandManager()._process_users_normal(users, Session(), fail_first(done))
    )
    assert done == ["second"]
    check_failure_shown(logs)


def test_user_first_gather_warns_and_goes_on(logs):
    async def gather(c, ele):
        if ele.name == "first":
            raise ValueError("boom")
        return {ele.id: ele.name}

    users = [creator("first"), creator("second")]
    data = asyncio.run(
        command.CommandManager()._gather_user_first_data(users, Session(), gather)
    )
    assert list(data.values()) == ["second"]
    check_failure_shown(logs)


def test_user_first_actions_warn_and_go_on(logs):
    done = []
    data = {
        n: {"ele": creator(n), "postcollection": SimpleNamespace()}
        for n in ("first", "second")
    }
    asyncio.run(
        command.CommandManager()._execute_user_first_actions(data, fail_first(done))
    )
    assert done == ["second"]
    check_failure_shown(logs)


def test_scraper_action_failure_warns_and_goes_on(logs, monkeypatch):
    # the download action raises for the first creator; the scraper's own
    # action step catches it, so the warning must come from there
    done = []

    async def downloader(username=None, **_):
        if username == "first":
            raise ValueError("boom")
        done.append(username)

    async def posts(ele, c=None):
        return SimpleNamespace(
            get_media_for_processing=lambda: [],
            get_posts_to_like=lambda: [],
            get_posts_for_text_download=lambda: [],
        )

    monkeypatch.setattr(command, "post_media_process", posts)
    monkeypatch.setattr(scraper, "downloader", downloader)
    monkeypatch.setattr(
        scraper.progress_utils, "setup_live", lambda *_, **__: contextlib.nullcontext()
    )
    monkeypatch.setattr(
        scraper.settings, "get_settings", lambda: SimpleNamespace(actions=["download"])
    )
    models = SimpleNamespace(
        get_num_scrape_selected_models=lambda: 2,
        mark_as_processed=lambda *_, **__: None,
    )
    stats = SimpleNamespace(update_and_print_stats=lambda *_, **__: None)
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=models, stats_manager=stats),
    )
    monkeypatch.setitem(scraper.ACTION_SCRIPTS, "download", lambda *_, **__: None)

    manager = scraper.scraperManager()
    users = [creator("first"), creator("second")]
    asyncio.run(
        manager._process_users_normal(users, Session(), manager._execute_user_action)
    )
    assert done == ["second"]
    check_failure_shown(logs, what=" download")


def interrupt_first(done):
    async def action(ele=None, **_):
        if ele.name == "first":
            raise KeyboardInterrupt
        done.append(ele.name)

    return action


def test_ctrl_c_still_stops_every_loop(logs, monkeypatch):
    # Ctrl+C isn't an Exception, so it passes the loops' handlers and stops
    # the run at once, with no "failed" warning
    async def posts(ele, c=None):
        return SimpleNamespace()

    async def gather(c, ele):
        raise KeyboardInterrupt

    monkeypatch.setattr(command, "post_media_process", posts)
    manager = command.CommandManager()
    users = [creator("first"), creator("second")]
    data = {
        n: {"ele": creator(n), "postcollection": SimpleNamespace()}
        for n in ("first", "second")
    }
    done = []
    runs = [
        manager._process_users_normal(users, Session(), interrupt_first(done)),
        manager._gather_user_first_data(users, Session(), gather),
        manager._execute_user_first_actions(data, interrupt_first(done)),
    ]
    for run in runs:
        with pytest.raises(KeyboardInterrupt):
            asyncio.run(run)
    assert done == []
    assert logs.normal.records == []


class InterruptWhenIdle(queue.Queue):
    # Ctrl+C while the daemon waits for its next job
    def get(self, *args, **kwargs):
        if self.empty():
            raise KeyboardInterrupt
        return super().get(*args, **kwargs)


def test_daemon_pass_failure_warns_and_goes_on(logs, monkeypatch):
    runs = []

    def failing_pass():
        raise ValueError("boom")

    jobs = InterruptWhenIdle()
    jobs.put(failing_pass)
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: None)
    monkeypatch.setattr(
        scraper, "scraperManager", lambda: SimpleNamespace(runner=lambda: runs.append(1))
    )
    monkeypatch.setattr(
        scraper.settings, "get_settings", lambda: SimpleNamespace(output_level="NORMAL")
    )
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(sync_models=lambda: None)),
    )
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(scraper, "set_schedule", lambda *args, **kwargs: None)

    with pytest.raises(KeyboardInterrupt):
        scraper.daemon_process()
    assert runs == [1]  # the next pass still ran
    assert jobs.unfinished_tasks == 0
    warnings = [r.getMessage() for r in logs.normal.records if r.levelno == logging.WARNING]
    assert "Daemon pass failed: ValueError: boom" in warnings
    assert not any("Traceback" in m for m in logs.normal.messages())
    assert any("Traceback" in m for m in logs.traces.messages())


@pytest.mark.parametrize("wakeup_installed", [False, True])
def test_scheduler_failure_warns_and_goes_on(logs, monkeypatch, wakeup_installed):
    # with the wake-up signal the loop polls every 0.1 s, but an error still
    # waits the normal interval
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.installed = wakeup_installed  # a flag only; no real handler is set
    joins = []

    class Jobs:
        def join(self):
            joins.append(1)
            if len(joins) == 1:
                raise ValueError("boom")
            wakeup.stopped = True  # the loop came round again; end the test

    sleeps = []
    monkeypatch.setattr(daemon_schedule, "jobqueue", Jobs())
    monkeypatch.setattr(daemon_schedule.time, "sleep", sleeps.append)
    monkeypatch.setattr(
        daemon_schedule.settings, "get_settings", lambda: SimpleNamespace(daemon=60)
    )
    daemon_schedule.set_schedule(lambda: None, wakeup=wakeup)
    assert joins == [1, 1]
    assert sleeps == [12]  # daemon 60 / 5: the normal interval, not 0.1 s
    warnings = [r.getMessage() for r in logs.normal.records if r.levelno == logging.WARNING]
    assert warnings == ["Daemon scheduler failed: ValueError: boom"]
    assert any("Traceback" in m for m in logs.traces.messages())


def test_repeating_scheduler_error_warns_once_per_interval(logs, monkeypatch):
    # an error on every round, with the wake-up signal's fast poll on: the
    # loop must wait the normal interval (1 s here) between rounds, so half a
    # second gives one warning, not thousands
    wakeup = daemon_schedule.DaemonWakeup()
    wakeup.installed = True  # a flag only; no real handler is set

    class Jobs:
        def join(self):
            raise ValueError("queue broken")

    monkeypatch.setattr(daemon_schedule, "jobqueue", Jobs())
    monkeypatch.setattr(
        daemon_schedule.settings, "get_settings", lambda: SimpleNamespace(daemon=5)
    )
    worker = threading.Thread(
        target=daemon_schedule.set_schedule, args=[lambda: None], kwargs={"wakeup": wakeup}
    )
    worker.start()
    time.sleep(0.5)
    wakeup.stopped = True
    worker.join(5)
    assert not worker.is_alive()
    warnings = [r for r in logs.normal.records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in warnings] == [
        "Daemon scheduler failed: ValueError: queue broken"
    ]


# --- one area of a creator's scrape ------------------------------------------

AREAS = [
    "Profile", "Purchased", "Messages", "Pinned", "Timeline", "Archived",
    "Highlights", "Stories", "Labels", "Streams",
]


def scrape_areas(monkeypatch, failing, free_min=0):
    """Run the real area fetchers for every area. The site calls under them
    raise for the areas in `failing` and return nothing for the rest."""

    def site_call(area):
        async def call(*_, **__):
            if area in failing:
                raise ValueError(f"{area} down")
            return []

        return call

    def profile_call(*_, **__):
        if "Profile" in failing:
            raise ValueError("Profile down")
        return {}

    monkeypatch.setattr(post.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(post.profile, "scrape_profile", profile_call)
    monkeypatch.setattr(post.paid, "get_paid_posts", site_call("Purchased"))
    monkeypatch.setattr(post.messages, "get_messages", site_call("Messages"))
    monkeypatch.setattr(post.pinned, "get_pinned_posts", site_call("Pinned"))
    monkeypatch.setattr(post.timeline, "get_timeline_posts", site_call("Timeline"))
    monkeypatch.setattr(post.archive, "get_archived_posts", site_call("Archived"))
    monkeypatch.setattr(post.highlights, "get_highlight_post", site_call("Highlights"))
    monkeypatch.setattr(post.highlights, "get_stories_post", site_call("Stories"))
    monkeypatch.setattr(post.labels_api, "get_labels", site_call("Labels"))
    monkeypatch.setattr(post.streams, "get_streams_posts", site_call("Streams"))

    async def no_db(*_, **__):
        return None

    for name in (
        "make_post_table_changes",
        "make_messages_table_changes",
        "make_stories_table_changes",
        "make_label_table_changes",
    ):
        monkeypatch.setattr(post.operations, name, no_db)
    monkeypatch.setattr(post, "set_after_checks", lambda *_: None)
    monkeypatch.setattr(post, "get_final_posts_area", lambda: AREAS)
    monkeypatch.setattr(post, "get_like_area", lambda: [])
    monkeypatch.setattr(post, "get_download_area", lambda: AREAS)
    monkeypatch.setattr(
        post.progress_utils, "setup_live", lambda *_, **__: contextlib.nullcontext()
    )
    run_settings = SimpleNamespace(
        post_id=None,
        skip_unavailable_content=False,
        command="main",
        text=False,
        system_free_min=free_min,
        timeline_strict=False,
    )
    monkeypatch.setattr(post.settings, "get_settings", lambda: run_settings)
    monkeypatch.setattr(post.free.settings, "get_settings", lambda: run_settings)
    monkeypatch.setattr(post.free, "get_free", lambda: 10)
    ele = SimpleNamespace(name="first", active=True)
    return asyncio.run(post.process_tasks(1, "first", ele))


def warning_messages(logs):
    return sorted(
        r.getMessage() for r in logs.normal.records if r.levelno == logging.WARNING
    )


@pytest.mark.parametrize("area", AREAS)
def test_a_failed_area_warns_and_the_others_still_come_back(logs, monkeypatch, area):
    collection = scrape_areas(monkeypatch, failing={area})
    assert collection is not None
    assert warning_messages(logs) == [f"[first] {area} failed: ValueError: {area} down"]
    assert not any("Traceback" in m for m in logs.normal.messages())
    assert any(
        "Traceback" in m and f"{area} down" in m for m in logs.traces.messages()
    )


def test_every_failed_area_is_named(logs, monkeypatch):
    scrape_areas(monkeypatch, failing={"Messages", "Timeline", "Labels"})
    assert warning_messages(logs) == [
        "[first] Labels failed: ValueError: Labels down",
        "[first] Messages failed: ValueError: Messages down",
        "[first] Timeline failed: ValueError: Timeline down",
    ]


def test_free_space_stop_is_shown_for_each_area(logs, monkeypatch):
    # the free-space check runs before an area's own error handling
    scrape_areas(monkeypatch, failing=set(), free_min=100)
    assert warning_messages(logs) == sorted(
        f"[first] {area} failed: Exception: Space min has been reached"
        for area in AREAS
    )


def test_a_failed_save_of_the_scrape_is_shown(logs, monkeypatch):
    # after the areas: saving their media fails for the whole creator
    async def areas(*_, **__):
        raise ValueError("save failed")

    monkeypatch.setattr(post, "process_tasks", areas)

    async def run():
        return await post.process_areas(SimpleNamespace(name="first"), 1, "first")

    assert asyncio.run(run()) is None
    assert warning_messages(logs) == ["[first] scrape failed: ValueError: save failed"]


@pytest.mark.parametrize("user_first", [False, True])
def test_a_failed_scrape_gives_one_warning_and_the_next_creator_runs(
    logs, monkeypatch, user_first
):
    # the real post_media_process: the scrape fails for the first creator, so
    # there's no collection to compare for strays or to act on
    async def no_tables(*_, **__):
        return None

    async def areas(model_id, username, ele, c=None):
        if username == "first":
            raise ValueError("save failed")
        return SimpleNamespace(all_unique_media=[], posts=[], all_media=[])

    async def no_media(*_, **__):
        return None

    async def no_unlocked(*_, **__):
        return []

    monkeypatch.setattr(post.operations, "table_init_create", no_tables)
    monkeypatch.setattr(post, "process_tasks", areas)
    monkeypatch.setattr(post, "batch_mediainsert", no_media)
    monkeypatch.setattr(post, "get_unlocked_media_ids", no_unlocked)
    monkeypatch.setattr(command, "post_media_process", post.post_media_process)

    done = []

    async def action(ele=None, postcollection=None):
        done.append(ele.name)

    manager = command.CommandManager()
    users = [creator("first"), creator("second")]
    if user_first:

        async def gather(c, ele):
            return {
                ele.id: {
                    "ele": ele,
                    "postcollection": await post.post_media_process(ele, c),
                }
            }

        async def run():
            data = await manager._gather_user_first_data(users, Session(), gather)
            await manager._execute_user_first_actions(data, action)

        asyncio.run(run())
    else:
        asyncio.run(manager._process_users_normal(users, Session(), action))
    assert done == ["second"]
    assert warning_messages(logs) == ["[first] scrape failed: ValueError: save failed"]


def test_a_scrape_with_no_errors_shows_nothing_new(logs, monkeypatch):
    collection = scrape_areas(monkeypatch, failing=set())
    assert collection is not None
    # the one line main shows here too, and nothing else
    assert logs.normal.messages() == ["Initialized PostCollection for first"]


def test_no_errors_logs_no_warning(logs, monkeypatch):
    async def posts(ele, c=None):
        return SimpleNamespace()

    monkeypatch.setattr(command, "post_media_process", posts)
    done = []
    users = [creator("second"), creator("third")]
    asyncio.run(
        command.CommandManager()._process_users_normal(users, Session(), fail_first(done))
    )
    assert done == ["second", "third"]
    assert logs.normal.records == []
