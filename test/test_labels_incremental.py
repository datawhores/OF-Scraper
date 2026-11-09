import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

import ofscraper.data.api.labels as labels


class FakeResponse:
    def __init__(self, data, status=200):
        self.status = status
        self._data = data

    async def json_(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeClient:
    """Serves a label's posts newest first, page_size at a time, by offset."""

    def __init__(self, ids, page_size=5, fail_at=None):
        self.posts = [{"id": i} for i in sorted(ids, reverse=True)]
        self.page_size = page_size
        self.fail_at = fail_at
        self.offsets = []

    def requests_async(self, url, **kwargs):
        offset = int(parse_qs(urlsplit(url).query)["offset"][0])
        self.offsets.append(offset)
        if offset == self.fail_at:
            return FakeResponse({}, status=429)
        page = self.posts[offset : offset + self.page_size]
        has_more = offset + self.page_size < len(self.posts)
        return FakeResponse({"list": page, "hasMore": has_more})


class FakeCache:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None, **kwargs):
        return self.data.get(key, default)

    def set(self, key, value, **kwargs):
        self.data[key] = value


@pytest.fixture(autouse=True)
def fake_cache(monkeypatch):
    store = FakeCache()
    monkeypatch.setattr(labels, "cache", store)
    return store


LABEL = {"id": 7, "name": "favourites"}
COMPLETE = labels.label_complete_key(1, 7)


@pytest.fixture(autouse=True)
def no_pending_marks():
    labels._finished_labels.clear()
    yield
    labels._finished_labels.clear()


def collect(client, known=None, track=False):
    async def run():
        out = []
        extra = {} if known is None else {"known": known}
        if track:
            extra["track"] = True
        async for _, batch in labels.scrape_posts_labels(client, LABEL, 1, **extra):
            out.extend(p["id"] for p in batch)
        return out

    return asyncio.run(run())


def test_first_scan_pages_through_every_post():
    client = FakeClient(range(1, 21))
    assert collect(client) == list(range(20, 0, -1))
    assert client.offsets == [0, 5, 10, 15]


def test_repeat_scan_stops_at_the_first_fully_recorded_page():
    client = FakeClient(range(1, 21))
    known = {str(i) for i in range(1, 21)}
    assert collect(client, known=known) == [20, 19, 18, 17, 16]
    assert client.offsets == [0]


def test_new_posts_are_still_returned_before_stopping():
    # 21-23 were added to the label since the last scan
    client = FakeClient(range(1, 24))
    known = {str(i) for i in range(1, 21)}
    ids = collect(client, known=known)
    assert ids[:3] == [23, 22, 21]
    assert set(range(21, 24)) <= set(ids)
    # page 1: 23-19 (new posts), page 2: 18-14 (all known) -> stop
    assert client.offsets == [0, 5]


def test_finished_scans_are_marked_complete_once_saved(fake_cache):
    collect(FakeClient(range(1, 21)), track=True)
    # not trusted until the run has saved label and media rows
    assert fake_cache.data[COMPLETE] is False
    labels.commit_finished_labels(1)
    assert fake_cache.data[COMPLETE] is True
    collect(FakeClient(range(1, 21)), known={str(i) for i in range(1, 21)}, track=True)
    labels.commit_finished_labels(1)
    assert fake_cache.data[COMPLETE] is True


def test_finished_scan_is_not_trusted_if_saving_fails(fake_cache):
    # e.g. the run is killed, or the label/media insert fails, after paging ends
    collect(FakeClient(range(1, 21)), track=True)
    labels.discard_finished_labels(1)
    labels.commit_finished_labels(1)
    assert fake_cache.data[COMPLETE] is False


def test_scan_cut_short_by_a_429_is_marked_incomplete(fake_cache):
    fake_cache.data[COMPLETE] = True
    client = FakeClient(range(1, 21), fail_at=5)
    assert collect(client, track=True) == [20, 19, 18, 17, 16]
    labels.commit_finished_labels(1)
    assert fake_cache.data[COMPLETE] is False


def test_check_mode_leaves_the_marks_alone(fake_cache):
    fake_cache.data[COMPLETE] = True
    collect(FakeClient(range(1, 21), fail_at=5))
    labels.commit_finished_labels(1)
    assert fake_cache.data[COMPLETE] is True


def run_known(monkeypatch, prechecks, db_ids, username="creator", missing=()):
    monkeypatch.setattr(labels, "get_after_pre_checks", lambda *a, **k: prechecks)

    async def fake_db(label, model_id=None, username=None, **kwargs):
        return db_ids[label.label_id]

    async def fake_missing(model_id, username):
        return {str(x) for x in missing}

    monkeypatch.setattr(labels, "get_all_labels_posts", fake_db)
    monkeypatch.setattr(labels, "get_posts_missing_media", fake_missing)
    return asyncio.run(
        labels.get_known_label_posts(
            [{"id": 7}, {"id": 8}], model_id=1, username=username
        )
    )


def mark_complete(fake_cache, *label_ids):
    for label_id in label_ids:
        fake_cache.data[labels.label_complete_key(1, label_id)] = True


def test_known_posts_are_read_per_label(monkeypatch, fake_cache):
    mark_complete(fake_cache, 7, 8)
    known = run_known(monkeypatch, None, {7: [1, 2], 8: []})
    assert known == {7: {"1", "2"}, 8: set()}


def test_integer_ids_from_the_database_match_the_api(monkeypatch, fake_cache):
    # the labels table returns ints, the API returns ints; the stop compares strings
    mark_complete(fake_cache, 7, 8)
    known = run_known(monkeypatch, None, {7: list(range(1, 21)), 8: []})
    client = FakeClient(range(1, 21))
    assert collect(client, known=known[7]) == [20, 19, 18, 17, 16]
    assert client.offsets == [0]


def test_full_scan_requests_ignore_recorded_posts(monkeypatch, fake_cache):
    # --after, incremental off or like/unlike, as for the timeline
    mark_complete(fake_cache, 7, 8)
    assert run_known(monkeypatch, 0, {7: [1], 8: [2]}) == {}


def test_without_a_username_every_label_is_scanned_fully(monkeypatch, fake_cache):
    # e.g. check mode, which calls get_labels without a username
    mark_complete(fake_cache, 7, 8)
    assert run_known(monkeypatch, None, {7: [1], 8: [2]}, username=None) == {}


def test_label_whose_last_scan_did_not_finish_is_scanned_fully(
    monkeypatch, fake_cache
):
    mark_complete(fake_cache, 8)
    assert run_known(monkeypatch, None, {7: [1], 8: [2]}) == {8: {"2"}}


def test_label_with_undownloaded_media_is_scanned_fully(monkeypatch, fake_cache):
    mark_complete(fake_cache, 7, 8)
    known = run_known(monkeypatch, None, {7: [1, 2], 8: [3]}, missing=[2])
    assert known == {8: {"3"}}


def test_posts_skipped_by_a_429_are_fetched_on_the_next_run(monkeypatch, fake_cache):
    # run 1: first scan, 429 on page 2; only page 1 gets recorded
    first = FakeClient(range(1, 21), fail_at=5)
    recorded = collect(first, track=True)
    labels.commit_finished_labels(1)
    # run 2: healthy; must reach posts 1-15 again
    known = run_known(monkeypatch, None, {7: recorded, 8: []})
    second = FakeClient(range(1, 21))
    assert collect(second, known=known.get(7)) == list(range(20, 0, -1))


def run_process_areas(monkeypatch, insert_fails):
    import ofscraper.data.posts.post as post

    async def fake_tasks(model_id, username, ele, c=None):
        # the Labels area finished paging label 7 during this run
        labels.mark_label_finished(model_id, 7)
        return SimpleNamespace(all_unique_media=[])

    async def fake_insert(*args, **kwargs):
        if insert_fails:
            raise RuntimeError("database is locked")

    monkeypatch.setattr(post, "process_tasks", fake_tasks)
    monkeypatch.setattr(post, "batch_mediainsert", fake_insert)
    # traceback_ is added by the app's logging setup, which tests don't run
    monkeypatch.setattr(
        post,
        "log",
        SimpleNamespace(
            traceback_=lambda *a, **k: None, debug=print, warning=lambda *a, **k: None
        ),
    )

    async def run():
        return await post.process_areas(SimpleNamespace(name="creator"), 1, "creator")

    asyncio.run(run())


def test_marks_are_written_after_the_media_rows_are_saved(monkeypatch, fake_cache):
    run_process_areas(monkeypatch, insert_fails=False)
    assert fake_cache.data.get(COMPLETE) is True


def test_marks_are_dropped_when_saving_media_rows_fails(monkeypatch, fake_cache):
    run_process_areas(monkeypatch, insert_fails=True)
    assert fake_cache.data.get(COMPLETE) is None
    assert 1 not in labels._finished_labels


def test_marks_are_dropped_when_the_pass_is_cancelled(monkeypatch, fake_cache):
    import ofscraper.data.posts.post as post

    async def cancelled_tasks(model_id, username, ele, c=None):
        labels.mark_label_finished(model_id, 7)
        raise asyncio.CancelledError()

    monkeypatch.setattr(post, "process_tasks", cancelled_tasks)

    async def run():
        return await post.process_areas(SimpleNamespace(name="creator"), 1, "creator")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
    assert 1 not in labels._finished_labels
    # a later pass in the same process doesn't commit the stale mark
    labels.commit_finished_labels(1)
    assert fake_cache.data.get(COMPLETE) is None


@pytest.mark.parametrize("username, tracked", [("creator", True), (None, False)])
def test_only_runs_with_a_username_track_finished_scans(monkeypatch, username, tracked):
    seen = {}

    async def fake_names(model_id, c=None):
        return [{"id": 7, "name": "favourites"}]

    async def fake_known(labels_, model_id, username):
        return {}

    async def fake_posts(labels_, model_id, c=None, known=None, track=False):
        seen["track"] = track
        return []

    monkeypatch.setattr(labels, "get_labels_data", fake_names)
    monkeypatch.setattr(labels, "get_known_label_posts", fake_known)
    monkeypatch.setattr(labels, "get_posts_for_labels", fake_posts)
    monkeypatch.setattr(labels, "update_check", lambda *a, **k: None)
    monkeypatch.setattr(labels.settings, "get_settings", lambda: SimpleNamespace(label=None))

    async def run():
        # get_labels is wrapped by @run; inside a running loop it returns the coroutine
        return await labels.get_labels(1, c=None, username=username)

    asyncio.run(run())
    assert seen["track"] is tracked


def test_missing_media_filter_matches_the_timeline(monkeypatch):
    rows = [
        {"media_id": 1, "post_id": 10, "media_type": "videos", "downloaded": 0, "unlocked": 1},
        {"media_id": 2, "post_id": 11, "media_type": "videos", "downloaded": 1, "unlocked": 1},
        {"media_id": 3, "post_id": 12, "media_type": "videos", "downloaded": 0, "unlocked": 1},
        {"media_id": 4, "post_id": 13, "media_type": "videos", "downloaded": 0, "unlocked": 0},
        {"media_id": 5, "post_id": 14, "media_type": "videos", "downloaded": 0, "unlocked": 1},
        {"media_id": 6, "post_id": 15, "media_type": "images", "downloaded": 0, "unlocked": 1},
    ]

    async def status(**kwargs):
        return rows

    async def downloaded(**kwargs):
        return {3}

    async def deleted(**kwargs):
        return {14}

    monkeypatch.setattr(labels, "get_model_media_status", status)
    monkeypatch.setattr(labels, "get_media_ids_downloaded_model", downloaded)
    monkeypatch.setattr(labels, "get_deleted_post_ids", deleted)
    monkeypatch.setattr(
        labels.settings,
        "get_settings",
        lambda: SimpleNamespace(mediatypes=["Videos"]),
    )
    assert asyncio.run(labels.get_posts_missing_media(1, "creator")) == {"10"}


def test_labels_are_paged_at_most_two_at_a_time(monkeypatch):
    real_getattr = labels.of_env.getattr
    monkeypatch.setattr(
        labels.of_env,
        "getattr",
        lambda key, *a, **k: 2 if key == "LABELS_CONCURRENCY" else real_getattr(key, *a, **k),
    )
    state = {"active": 0, "peak": 0}

    async def gen(label):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        for page in range(3):
            await asyncio.sleep(0)
            yield label, [{"id": label["id"] * 100 + page}]
        state["active"] -= 1

    label_list = [{"id": i, "name": str(i)} for i in range(1, 6)]
    result = asyncio.run(
        labels.process_tasks_get_posts_for_labels(
            [gen(lab) for lab in label_list], label_list
        )
    )
    assert state["peak"] == 2
    assert sum(len(r["posts"]) for r in result) == 15
