"""Cart batches report each file as it finishes, and retry only failures (#439)."""

import asyncio
import logging
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ofscraper.commands.check as check
from ofscraper.commands.scraper.actions.download import download
from ofscraper.commands.scraper.actions.download import run as workers


def _media(mid):
    return SimpleNamespace(
        id=mid, filename=f"file{mid}.jpg", post=object(),
        mark_download_succeeded=Mock(), mark_download_skipped=Mock(),
        mark_download_failed=Mock(),
    )


@pytest.fixture
def batch(monkeypatch):
    updates = Mock()
    refill = Mock()
    cdm = Mock(return_value=True)
    record = Mock()
    monkeypatch.setattr(check.app, "app", SimpleNamespace(update_cell_state=updates), raising=False)
    monkeypatch.setattr(check, "_record_row_file", record)
    monkeypatch.setattr(check, "data_refill", refill)
    monkeypatch.setattr(check, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(check.network, "check_cdm", cdm)
    monkeypatch.setattr(check.operations, "table_init_create", Mock())
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(
        current_model_manager=SimpleNamespace(get_model=lambda _: SimpleNamespace(
            active=True, expired_string=None))))
    monkeypatch.setattr(check._process_user_batch, "counter", 0)
    media = [_media(i) for i in range(4)]
    fresh = [_media(i) for i in range(4)]
    collection = SimpleNamespace(find_media_item=lambda mid: media[mid])
    monkeypatch.setitem(check.check_user_dict, "1", {"collection": collection})

    def refresh(_):
        collection.find_media_item = lambda mid: fresh[mid]
    refill.side_effect = refresh

    def go():
        posts = [m.post for m in media]
        rows = [(str(m.id), {}) for m in media]
        check._process_user_batch("a creator", 1, media, posts, rows)
        return posts

    return SimpleNamespace(go=go, media=media, fresh=fresh, updates=updates,
                           refill=refill, cdm=cdm, record=record)


def test_cart_sends_all_files_and_updates_each_row_before_batch_returns(monkeypatch, batch):
    calls = []

    def process(username, model_id, media, posts, on_result=None):
        calls.append(list(media))
        # Completion order differs from cart order.
        for m, result, style in [(media[3], "downloaded", "bold green"),
                                 (media[1], "skipped", "bold bright_yellow"),
                                 (media[0], "downloaded", "bold green"),
                                 (media[2], "downloaded", "bold green")]:
            on_result(m, result)
            batch.updates.assert_called_with(str(m.id), f"[{result}]", style)
        return (0, 0, 3, 1, 0)

    monkeypatch.setattr(check, "process_dicts", process)
    batch.go()
    assert calls == [batch.media]
    assert batch.updates.call_count == 4
    assert batch.record.call_count == 3
    batch.refill.assert_not_called()
    batch.go()
    batch.cdm.assert_called_once()


def test_failed_files_retry_together_once_with_fresh_media(monkeypatch, batch):
    calls = []
    original = list(batch.media)

    def process(username, model_id, media, posts, on_result=None):
        calls.append(list(media))
        if len(calls) == 1:
            for m, result in zip(media, ["downloaded", "skipped", "failed", "failed"]):
                on_result(m, result)
        else:
            batch.refill.assert_called_once_with(1)
            check.time.sleep.assert_called_once_with(1)
            assert media == batch.fresh[2:]
            assert posts == [m.post for m in batch.fresh[2:]]
            on_result(media[0], "downloaded")
            on_result(media[1], "failed")
        return (0, 0, 1, 0, 1)

    monkeypatch.setattr(check, "process_dicts", process)
    posts = batch.go()
    assert calls == [original, batch.fresh[2:]]
    assert batch.updates.call_args_list == [
        (("0", "[downloaded]", "bold green"),),
        (("1", "[skipped]", "bold bright_yellow"),),
        (("2", "[downloaded]", "bold green"),),
        (("3", "[failed]", "bold red"),),
    ]
    assert batch.media == original[:2] + [batch.fresh[2], original[3]]
    assert posts == [m.post for m in batch.media]


def test_unreported_file_is_failed_after_one_refill_and_retry(monkeypatch, batch, caplog):
    calls = []

    def process(username, model_id, media, posts, on_result=None):
        calls.append([m.id for m in media])
        for m in media:
            if m.id != 3:
                on_result(m, "downloaded")
        return (0, 0, 0, 0, 0)

    monkeypatch.setattr(check, "process_dicts", process)
    with caplog.at_level(logging.INFO, logger="shared"):
        batch.go()
    assert calls == [[0, 1, 2, 3], [3]]
    batch.refill.assert_called_once_with(1)
    check.time.sleep.assert_called_once_with(1)
    assert batch.updates.call_args_list == [
        (("0", "[downloaded]", "bold green"),),
        (("1", "[downloaded]", "bold green"),),
        (("2", "[downloaded]", "bold green"),),
        (("3", "[failed]", "bold red"),),
    ]
    assert caplog.messages.count("Download failed for file3.jpg.") == 1


@pytest.mark.parametrize("callback", [False, True], ids=["normal-scrape", "callback"])
def test_downloader_results_totals_concurrency_and_log(monkeypatch, caplog, callback):
    media = [_media(i) for i in range(5)]
    # Exercise successful media types, intentional skip, and a raised failure.
    outcomes = {0: "images", 1: "videos", 2: "audios", 3: "forced_skipped"}
    received = []
    active = 0
    peak = 0
    release = None

    async def fake_download(c, item, model_id, username):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=2)
        await asyncio.sleep(0)
        active -= 1
        if item.id == 4:
            raise RuntimeError("transfer failed")
        return outcomes[item.id], 10

    @asynccontextmanager
    async def session():
        yield object()

    monkeypatch.setattr(download.settings, "get_settings", lambda: SimpleNamespace(text=False, text_only=False))
    monkeypatch.setattr(download, "get_max_workers", lambda: 2)
    monkeypatch.setattr(download.manager, "Manager", SimpleNamespace(session=SimpleNamespace(get_download_session=session)))
    monkeypatch.setattr(download.progress_utils, "setup_live", lambda _: nullcontext())
    monkeypatch.setattr(download, "setDirectoriesDate", Mock())
    monkeypatch.setattr(download.cache, "close", Mock())
    monkeypatch.setattr(download.progress_updater, "download", SimpleNamespace(
        add_overall_task=Mock(return_value=1), update_overall_task=Mock(), remove_overall_task=Mock()))
    monkeypatch.setattr(workers, "download", fake_download)
    monkeypatch.setattr(workers, "get_medialog", lambda _: "file")
    monkeypatch.setattr(workers, "log_download_progress", Mock())

    def init():
        for attr in ("video_count", "audio_count", "photo_count", "forced_skipped", "skipped", "total_bytes_downloaded", "total_bytes"):
            monkeypatch.setattr(download.common_globals, attr, 0, raising=False)
        # Executor cleanup is still exercised by process_dicts.
        from concurrent.futures import ThreadPoolExecutor
        monkeypatch.setattr(download.common_globals, "thread", ThreadPoolExecutor(1), raising=False)
        monkeypatch.setattr(download.common_globals, "log", Mock())

    monkeypatch.setattr(download.common_globals, "mainProcessVariableInit", init)

    async def go():
        nonlocal release
        release = asyncio.Event()
        kwargs = {"on_result": lambda m, result: received.append((m.id, result))} if callback else {}
        return await download.process_dicts("a creator", 1, media, [], **kwargs)

    with caplog.at_level(logging.INFO, logger="shared"):
        totals = asyncio.run(go())
    assert totals == (1, 1, 1, 1, 1)
    assert peak == 2
    assert caplog.messages == ["Downloading up to 2 files at a time"]
    assert sorted(received) == ([(0, "downloaded"), (1, "downloaded"), (2, "downloaded"),
                                 (3, "skipped"), (4, "failed")] if callback else [])
    media[0].mark_download_succeeded.assert_called_once()
    media[3].mark_download_skipped.assert_called_once()
    media[4].mark_download_failed.assert_called_once()
