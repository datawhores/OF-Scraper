"""What each area's page consumer does with the pages its workers yield.

Every API area merges pages from concurrent workers through a queue. These
tests pin down, per area: the pages progress bar (descriptions and page
count), which items are kept (de-duplication), the log lines, that a worker
that raises is logged and does not stop the others, and whether workers are
stop-tracked fetch tasks.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import ofscraper.utils.live.updater as updater
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.data.api import (
    archive,
    highlights,
    labels,
    messages,
    paid,
    pinned,
    streams,
    timeline,
)
from ofscraper.data.api.common.logs import logs as api_logs
from ofscraper.data.api.subscriptions import lists


class Recorder:
    def __init__(self):
        self.progress = []
        self.logs = []
        self.fetch_tasks = 0


class Progress:
    def __init__(self, rec, name):
        self.rec = rec
        self.name = name

    def add_overall_task(self, description, **kwargs):
        self.rec.progress.append((self.name, "add", description, kwargs))
        return f"{self.name}-task"

    def update_overall_task(self, task, description=None, **kwargs):
        self.rec.progress.append((self.name, "update", task, description))

    def remove_overall_task(self, task):
        self.rec.progress.append((self.name, "remove", task))


class Handler(logging.Handler):
    def __init__(self, rec):
        super().__init__(level=1)
        self.rec = rec

    def emit(self, record):
        self.rec.logs.append((record.levelno, record.getMessage()))


@pytest.fixture
def rec(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(updater, "api", Progress(rec, "api"))
    monkeypatch.setattr(updater, "userlist", Progress(rec, "userlist"))
    monkeypatch.setattr(api_logs, "is_trace", lambda: True)
    shared = logging.getLogger("shared")

    def traceback_(arg, *a, **k):
        # the formatted traceback names files and lines; keep only its kind
        text = repr(arg) if isinstance(arg, BaseException) else "<traceback>"
        rec.logs.append(("TRACEBACK", text))

    monkeypatch.setattr(shared, "traceback_", traceback_, raising=False)
    monkeypatch.setattr(shared, "trace", lambda msg: shared.log(5, msg), raising=False)
    real_create = stop.create_fetch_task

    def create_fetch_task(coro):
        rec.fetch_tasks += 1
        return real_create(coro)

    monkeypatch.setattr(stop, "create_fetch_task", create_fetch_task)
    handler = Handler(rec)
    old_level = shared.level
    shared.addHandler(handler)
    shared.setLevel(1)
    yield rec
    shared.removeHandler(handler)
    shared.setLevel(old_level)


def item(n):
    return {"id": n}


async def pages(*batches, fail=False):
    for batch in batches:
        await asyncio.sleep(0)
        yield batch
    if fail:
        raise RuntimeError("boom")


def post_workers(make=item):
    """Three workers: one repeats a post and sends an empty page, one fails."""
    return [
        pages([make(1), make(2)], [], [make(2), make(3)]),
        pages([make(4)], fail=True),
        pages([make(5)]),
    ]


def run(coro):
    return asyncio.run(coro)


def ids(data):
    return [x["id"] for x in data]


def progress_updates(prefix, count, name="api"):
    task = f"{name}-task"
    return (
        [(name, "add", f"{prefix}: 0", {"visible": True})]
        + [(name, "update", task, f"{prefix}: {n}") for n in range(1, count + 1)]
        + [(name, "remove", task)]
    )


def non_trace(rec):
    return [entry for entry in rec.logs if entry[0] != 5]


def trace_titles(rec):
    return [msg for level, msg in rec.logs if level == 5 and "current item" not in msg]


# Pages arrive round-robin from the three workers: A1, B1, C1, A2 (empty), A3.
ORDER = [1, 2, 4, 5, 3]
FAILED = [("TRACEBACK", "RuntimeError('boom')"), ("TRACEBACK", "<traceback>")]


def ids_line(name, values):
    return (10, f"[bold]\\[{name} In progress ids][/bold]  {values}")


POST_AREAS = {
    # name: (consumer, progress prefix, debug "in progress" name or None,
    #        trace label, final debug lines, final trace title)
    "timeline": (
        timeline.process_tasks,
        "Timeline Content Pages Progress",
        "Timeline",
        "Timeline task",
        [],
        None,
    ),
    "archived": (
        archive.process_tasks_batch,
        "Archived Content Pages Progress",
        None,
        "Archived task",
        [],
        None,
    ),
    "streams": (
        streams.process_tasks_batch,
        "Streams Content Pages Progress",
        None,
        "Streams task",
        [
            "[bold]Streams Final ids[/bold]  [1, 2, 4, 5, 3]",
            "[bold]Streams Final count[bold]: 5 post(s) ",
        ],
        "Streams final",
    ),
    "messages": (
        messages.process_tasks,
        "Message Content Pages Progress",
        None,
        "Messages task",
        [
            "[bold]Messages Final ids[/bold]  [1, 2, 4, 5, 3]",
            "[bold]Messages Final count[bold]: 5 post(s) ",
        ],
        "Messages final",
    ),
    "pinned": (
        pinned.process_tasks_batch,
        "Pinned Content Pages Progress",
        "Pinned",
        "Pinned task",
        [
            "[bold]Pinned Final ids[/bold]  [1, 2, 4, 5, 3]",
            "[bold]Pinned Final count[bold]: 5 post(s) ",
        ],
        "Pinned final",
    ),
    "paid": (
        paid.process_tasks,
        "Paid Content Pages Progress",
        "Paid",
        "Purchased tasks",
        ["[bold]Paid Final count[bold]: 5 post(s) "],
        "Purchased final",
    ),
    "stories": (
        highlights.process_stories_tasks,
        "Stories Pages Progress",
        None,
        "Stories task",
        ["[bold]Stories Final ids[/bold]  [1, 2, 4, 5, 3]"],
        "Stories final",
    ),
    "highlight posts": (
        highlights.process_task_highlights,
        "Highlight Content Progress",
        None,
        "Highlights list posts task",
        [
            "[bold]Highlight List Posts Final ids[/bold]  [1, 2, 4, 5, 3]",
            "[bold]Highlight List Posts Final count[bold]: {5} post(s) ",
        ],
        "Highlights lists posts final",
    ),
    "label names": (
        labels.process_tasks_labels,
        "Label Names Pages Progress",
        "Label Names",
        "Labels names tasks",
        [
            "[bold]Labels Names Final ids[/bold]  [1, 2, 4, 5, 3]",
            "[bold]Label Names Final count[bold]: 5 labels ",
        ],
        "Labels names final",
    ),
}


@pytest.mark.parametrize("area", POST_AREAS)
def test_post_pages_are_merged_once_each(rec, area):
    consumer, prefix, ids_name, trace_label, final, final_trace = POST_AREAS[area]

    data = run(consumer(post_workers()))

    assert ids(data) == ORDER
    # every page counts, the empty one included; the failed worker's end doesn't
    assert rec.progress == progress_updates(prefix, 5)
    assert rec.fetch_tasks == 3
    expected = []
    for new in ([1, 2], [4], [5], [3]):
        if ids_name:
            expected.append(ids_line(ids_name, new))
    # the failure is logged when worker B ends, after its page was merged
    logged = non_trace(rec)
    assert [entry for entry in logged if entry[0] == "TRACEBACK"] == FAILED
    assert [entry for entry in logged if entry[0] == 10] == (
        expected + [(10, line) for line in final]
    )
    titles = [
        f"[bold]\\[{trace_label} In progress raw data][/bold] total item"
    ] * 4
    if final_trace:
        titles.append(f"[bold]{final_trace} Final Count[bold] ")
    assert trace_titles(rec) == titles


def test_highlight_list_keeps_each_id_once(rec):
    data = run(highlights.process_task_get_highlight_list(post_workers(lambda n: n)))

    assert data == ORDER
    assert rec.progress == progress_updates("Highlights List Progress", 5)
    assert rec.fetch_tasks == 3
    assert non_trace(rec) == FAILED + [
        (10, "[bold]Highlight List Final count[bold]: 5 highlights "),
    ]
    assert trace_titles(rec) == ["[bold]Highlights list final Final Count[bold] "]


def test_all_paid_keeps_repeats_and_caches_ids(rec, monkeypatch):
    stored = {}
    monkeypatch.setattr(
        paid.cache, "set", lambda key, value, **k: stored.__setitem__(key, value)
    )

    data = run(paid.process_tasks_all_paid(post_workers()))

    assert ids(data) == [1, 2, 4, 5, 2, 3]
    assert stored == {"purchased_all": [1, 2, 4, 5, 2, 3]}
    assert rec.progress == progress_updates("[Scrape Paid] Pages Progress", 5)
    assert rec.fetch_tasks == 3
    assert non_trace(rec) == FAILED
    assert trace_titles(rec) == [
        "[bold]\\[Purchased all users tasks In progress raw data][/bold] total item"
    ] * 4 + ["[bold]Purchased all users final Final Count[bold] "]


def test_all_paid_stop_requested_skips_the_cache(rec, monkeypatch):
    stored = {}
    monkeypatch.setattr(
        paid.cache, "set", lambda key, value, **k: stored.__setitem__(key, value)
    )
    stop.clear()
    stop.requested.set()
    try:
        with pytest.raises(asyncio.CancelledError):
            run(paid.process_tasks_all_paid([pages([item(1)])]))
    finally:
        stop.clear()
    assert stored == {}


def test_label_posts_are_kept_per_label(rec, monkeypatch):
    monkeypatch.setattr(
        labels.of_env,
        "getattr",
        lambda key, *a, **k: 1 if key == "LABELS_CONCURRENCY" else None,
    )
    first, second = {"id": "a"}, {"id": "b"}

    def tagged(label, *batches, fail=False):
        async def gen():
            async for batch in pages(*batches, fail=fail):
                yield label, batch

        return gen()

    workers = [
        tagged(first, [item(1), item(2)], [], [item(2), item(3)]),
        tagged(second, [item(2)], fail=True),
        tagged(first, [item(3), item(4)]),
    ]

    data = run(labels.process_tasks_get_posts_for_labels(workers, [first, second]))

    assert [(label["id"], ids(label["posts"])) for label in data] == [
        ("a", [1, 2, 3, 4]),
        ("b", [2]),
    ]
    assert all("seen" not in label for label in data)
    assert rec.progress == progress_updates("Labels Progress", 5)
    assert rec.fetch_tasks == 3
    logged = non_trace(rec)
    assert logged == [
        ids_line("Label Content", [1, 2]),
        ids_line("Label Content", [3]),
        *FAILED,
        ids_line("Label Content", [2]),
        ids_line("Label Content", [4]),
        (10, "[bold]All Labels Content Final ids[/bold]  [1, 2, 3, 4, 2]"),
        (10, "[bold]Labels Individual Content Final ids[/bold] \na:[1, 2, 3, 4]\nb:[2]"),
        (10, "[bold]All Labels Content Final count[bold]: 5 post(s) "),
        (
            10,
            "[bold]Labels Individual Content -> Final Count[bold] \na:4 posts\nb:1 posts",
        ),
    ]


def test_list_users_merge_without_fetch_tracking(rec, monkeypatch):
    @asynccontextmanager
    async def session(**kwargs):
        yield object()

    monkeypatch.setattr(
        lists.manager,
        "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_subscription_session=session)),
    )
    workers = iter(post_workers())
    monkeypatch.setattr(lists, "scrape_list_members", lambda c, entry, **kwargs: next(workers))

    data = run(lists.get_list_users([{"id": 1}, {"id": 2}, {"id": 3}]))

    assert ids(data) == [1, 2, 4, 5, 3]
    assert rec.progress == progress_updates(
        "UserList Users Pages Progress", 5, name="userlist"
    )
    # list members aren't fetched under a stop-tracked fetch
    assert rec.fetch_tasks == 0
    assert non_trace(rec) == FAILED + [
        (10, "[bold]users count without Dupes[/bold] 5 found"),
    ]
