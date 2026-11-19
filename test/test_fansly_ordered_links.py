"""Fansly runs that need the whole list (--max-count, a sort) fetch each
chunk's links just before downloading it (sites/fansly/pipeline.py).

Those runs scan everything before the first download, so their links were up
to an hour old when used, and Fansly links are signed for the address that
asked. They now keep the scan and the selection as they were and download
through the pipeline's queue, asking ``account/media`` for each chunk's links
right before the chunk is queued.
"""

import copy
from types import SimpleNamespace

import pytest

import ofscraper.filters.media.filters as filters
import ofscraper.sites.fansly.pipeline as pipeline
from ofscraper.classes.of.posts import Post
from ofscraper.managers.postcollection import PostCollection

from test_fansly_pipeline import (  # noqa: F401  (settings_stub, harness are fixtures)
    MODEL_ID,
    NAME,
    equivalence_pages,
    harness,
    settings_stub,
)
from test_fansly_refresh_link import make_ele, signed


class Collection:
    """A finished scan: the selected media, in download order."""

    def __init__(self, media):
        self.media = media

    def get_media_to_download(self):
        return list(self.media)

    def get_posts_for_text_download(self):
        return []


def account_media_item(n, tag):
    """accountMedia ``n`` with every link signed as ``tag``."""
    item = signed(tag)
    item["id"] = str(9_000 + n)
    item["media"]["id"] = str(8_000 + n)
    return item


def signature(ele):
    return ele.url.split("Signature=")[1].split("&")[0]


@pytest.fixture
def answers(harness, monkeypatch):
    """``account/media``: each call answers every id asked, signed as
    ``call<k>``, except the ids in ``left_out``."""
    state = SimpleNamespace(calls=[], left_out=set(), error=None)

    async def account_media(c, ids):
        state.calls.append(list(ids))
        harness.events.append(f"account/media call {len(state.calls)}")
        if state.error:
            raise state.error
        tag = f"call{len(state.calls)}"
        return [
            account_media_item(int(i) - 9_000, tag)
            for i in ids
            if int(i) - 9_000 not in state.left_out
        ]

    monkeypatch.setattr(pipeline.fansly_api, "account_media", account_media)
    monkeypatch.setattr(pipeline.fansly_api, "ACCOUNT_MEDIA_BATCH", 3)
    return state


def scanned(count):
    """``count`` Fansly files as the scan left them, with links signed then."""
    return [make_ele(account_media_item(n, "scan")) for n in range(count)]


def run_with_urls(harness, items):
    """Run the pipeline on a finished scan; the link each file downloads with."""
    used = {}

    def remember(ele):
        async def hook(_):
            used[ele.id] = (signature(ele), ele.media["fansly"]["media"])

        return hook

    for item in items:
        harness.on_download[item.id] = remember(item)
    harness.run(collection=Collection(items))
    return used


def test_each_file_downloads_with_the_links_of_its_chunks_call(harness, answers):
    items = scanned(7)
    used = run_with_urls(harness, items)
    assert answers.calls == [
        [str(9_000 + n) for n in range(0, 3)],
        [str(9_000 + n) for n in range(3, 6)],
        [str(9_000 + 6)],
    ]
    assert harness.downloads == [item.id for item in items]
    for n, item in enumerate(items):
        tag = f"call{n // 3 + 1}"
        link, raw = used[item.id]
        assert link == f"signature-{tag}"
        # the stream downloader reads its links from the raw Media
        assert raw == account_media_item(n, tag)["media"]


def test_the_next_chunks_call_waits_until_this_chunk_is_downloading(harness, answers):
    items = scanned(7)
    run_with_urls(harness, items)
    events = harness.events
    assert events.index("account/media call 1") < events.index(f"download {items[0].id}")
    # the queue holds two files for one worker, so the second call comes only
    # after the first chunk's first file has started
    assert events.index(f"download {items[0].id}") < events.index("account/media call 2")
    assert events.index(f"download {items[3].id}") < events.index("account/media call 3")


def test_a_file_the_answer_leaves_out_downloads_with_its_scan_link(harness, answers):
    items = scanned(3)
    answers.left_out = {1}
    used = run_with_urls(harness, items)
    assert harness.downloads == [item.id for item in items]
    assert [used[item.id][0] for item in items] == [
        "signature-call1", "signature-scan", "signature-call1",
    ]


def test_a_failed_call_leaves_the_scan_links(harness, answers):
    items = scanned(4)
    answers.error = RuntimeError("boom")
    used = run_with_urls(harness, items)
    assert harness.downloads == [item.id for item in items]
    assert {used[item.id][0] for item in items} == {"signature-scan"}


def malformed(harness, answers, monkeypatch, answer):
    items = scanned(3)

    async def account_media(c, ids):
        answers.calls.append(list(ids))
        return answer

    monkeypatch.setattr(pipeline.fansly_api, "account_media", account_media)
    used = run_with_urls(harness, items)
    assert harness.downloads == [item.id for item in items]
    assert {used[item.id][0] for item in items} == {"signature-scan"}
    assert "processed" in harness.events


@pytest.mark.parametrize(
    "answer",
    [
        [{"id": "9000", "media": "not a media"}, {"id": "9001", "preview": 5}],
        [{"id": "9000", "media": {"id": "8000", "locations": "nonsense"}}],
    ],
    ids=["bad-items", "bad-locations"],
)
def test_a_malformed_answer_keeps_the_scan_links_and_the_run_goes_on(
    harness, answers, monkeypatch, answer
):
    malformed(harness, answers, monkeypatch, answer)


def test_an_answer_that_is_not_a_list_keeps_the_scan_links(harness, answers, monkeypatch):
    """Handled before the malformed-item fix too; kept so it stays that way."""
    malformed(harness, answers, monkeypatch, {"unexpected": "shape"})


def test_files_left_waiting_too_long_get_new_links_before_they_are_queued(
    harness, answers, monkeypatch
):
    """Big files: a chunk's last files would wait for the ones before them.
    Links older than FRESH_FOR are fetched again before a file is queued."""
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(pipeline, "_clock", lambda: clock.now)
    monkeypatch.setattr(pipeline, "FRESH_FOR", 10)
    monkeypatch.setattr(pipeline.fansly_api, "ACCOUNT_MEDIA_BATCH", 6)
    called_at = []
    real = pipeline.fansly_api.account_media

    async def timed(c, ids):
        called_at.append(clock.now)
        return await real(c, ids)

    monkeypatch.setattr(pipeline.fansly_api, "account_media", timed)
    items = scanned(12)
    ages = {}

    def slow(ele):
        async def hook(_):
            tag = signature(ele).split("call")[1]
            ages[ele.id] = clock.now - called_at[int(tag) - 1]
            clock.now += 6  # each download takes 6 seconds

        return hook

    for item in items:
        harness.on_download[item.id] = slow(item)
    harness.run(collection=Collection(items))
    assert harness.downloads == [item.id for item in items]
    # queued with links at most 10 s old, then behind at most two files (12 s)
    assert max(ages.values()) <= 10 + 12
    # two chunks of 6 would have been 2 calls; the waits add the rest
    assert len(answers.calls) > 2


def test_the_scan_stops_with_the_error_when_every_worker_has_ended(harness, answers):
    items = scanned(7)

    async def die(_):
        raise RuntimeError("worker broke")

    harness.on_download[items[0].id] = die
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run(collection=Collection(items))


def test_no_links_are_fetched_once_every_worker_has_ended(harness, answers, monkeypatch):
    # one file per call, so the queue has room when the only worker ends
    monkeypatch.setattr(pipeline.fansly_api, "ACCOUNT_MEDIA_BATCH", 1)
    items = scanned(5)

    async def die(_):
        raise RuntimeError("worker broke")

    harness.workers = 1
    harness.on_download[items[0].id] = die
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run(collection=Collection(items))
    ended = harness.events.index(f"download {items[0].id}")
    assert not [e for e in harness.events[ended:] if e.startswith("account/media")]


def test_a_worker_that_ends_on_the_last_file_fails_the_run(harness, answers):
    # nothing is left in the queue when it ends: the run must not end as a
    # success with a file undone
    items = scanned(3)

    async def die(_):
        raise RuntimeError("worker broke")

    harness.workers = 1
    harness.on_download[items[-1].id] = die
    with pytest.raises(RuntimeError, match="worker broke"):
        harness.run(collection=Collection(items))
    assert harness.downloads == [item.id for item in items[:-1]]


def test_files_without_an_account_media_id_make_no_call(harness, answers):
    items = scanned(2)
    for item in items:
        del item.media["fansly"]
    harness.run(collection=Collection(items))
    assert answers.calls == []
    assert harness.downloads == [item.id for item in items]


def test_the_scan_recorded_the_areas_so_the_run_does_not_again(harness, answers):
    harness.run(collection=Collection(scanned(2)))
    assert "after check" not in harness.events
    assert "strays" not in harness.events
    assert harness.cache == {}
    assert "stats" in harness.events and "processed" in harness.events


# ------------------------------------------------------------------ same list, same order


def full_list(pages):
    collection = PostCollection(model_id=MODEL_ID, username=NAME)
    for area, posts in pages:
        responsetype = "Timeline" if area == "Timeline" else None
        collection.add_posts(
            [Post(copy.deepcopy(p), MODEL_ID, NAME, responsetype) for p in posts],
            actions=["download"],
        )
    return collection


@pytest.mark.parametrize(
    "change",
    [
        {"max_post_count": 4},
        {"mediasort": "text"},
        {"mediasort": "text", "media_desc": True},
        {"mediasort": "date", "media_desc": True},
        {"max_post_count": 3, "mediasort": "date", "media_desc": True},
    ],
    ids=["max-count", "sort", "sort-desc", "date-desc", "max-count-date-desc"],
)
def test_the_files_and_their_order_match_the_scan_first_path(
    harness, settings_stub, monkeypatch, answers, change
):
    for key, value in change.items():
        setattr(settings_stub, key, value)
    monkeypatch.setattr(filters.me_util, "get_id", lambda: 999)
    pages = equivalence_pages()
    expected = [m.id for m in full_list(pages).get_media_to_download()]
    assert expected
    harness.run(collection=full_list(pages))
    assert harness.downloads == expected
