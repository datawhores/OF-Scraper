"""Stop cancels transfers, preserves Part files, and leaves the app running (#440)."""

import asyncio
import queue
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ofscraper.classes.table.app as table
import ofscraper.commands.scraper.scraper as scraper
from ofscraper.commands.scraper.actions.download import download, run as workers
from ofscraper.commands.scraper.actions.download.managers import main_download, alt_download
from ofscraper.managers.stats import DownloadStats, StatsManager


def test_stats_count_stopped_separately_and_omit_unstarted(caplog):
    media = [SimpleNamespace(download_stopped=True, download_attempted=True,
                             download_succeeded=False),
             SimpleNamespace(download_unstarted=True, download_attempted=False)]
    stats = DownloadStats("download")
    manager = StatsManager()
    manager._update_download_stats_helper(stats, media)
    assert stats.failed_count == stats.skipped_count == 0
    assert stats.stopped_count == 1
    assert "1 stopped" in str(stats)
    manager._stats["a creator"]["download"] = stats
    manager.print_global_summary()
    assert "STOPPED:     1 overall" in caplog.text


@pytest.fixture
def stop_signal():
    from ofscraper.commands.scraper.actions.download import stop
    stop.clear()
    yield stop
    stop.clear()


@pytest.mark.parametrize("drm", [False, True], ids=["normal", "drm"])
def test_stop_running_batch_keeps_part_and_never_finalises(
    monkeypatch, tmp_path, stop_signal, drm
):
    stop = stop_signal
    parts = []
    media = [SimpleNamespace(id=i, url="file", mpd=None, filename="file",
                             post_id=1, mediatype="videos", add_size=Mock(),
                             mark_download_failed=Mock(), mark_download_succeeded=Mock())
             for i in range(4)]
    progress = SimpleNamespace(add_overall_task=Mock(return_value=1),
                               remove_overall_task=Mock(), update_overall_task=Mock())
    received = []
    marked = AsyncMock()
    moved = Mock()
    after = AsyncMock()

    @asynccontextmanager
    async def session():
        yield object()

    def init():
        g = download.common_globals
        g.set_up_contexvars()
        for name in ("photo_count", "video_count", "audio_count", "skipped",
                     "forced_skipped", "stopped", "total_bytes", "total_bytes_downloaded"):
            monkeypatch.setattr(g, name, 0, raising=False)
        monkeypatch.setattr(g, "thread", ThreadPoolExecutor(1), raising=False)
        monkeypatch.setattr(g, "sem", asyncio.Semaphore(1), raising=False)
        monkeypatch.setattr(g, "log", Mock())

    monkeypatch.setattr(download.common_globals, "mainProcessVariableInit", init)
    monkeypatch.setattr(download.settings, "get_settings", lambda: SimpleNamespace(text=False, text_only=False, download_limit=0))
    monkeypatch.setattr(download, "get_max_workers", lambda: 2)
    monkeypatch.setattr(download.manager, "Manager", SimpleNamespace(session=SimpleNamespace(get_download_session=session)))
    monkeypatch.setattr(download.progress_utils, "setup_live", lambda _: nullcontext())
    monkeypatch.setattr(download.progress_updater, "download", progress)
    monkeypatch.setattr(download, "setDirectoriesDate", Mock())
    monkeypatch.setattr(download.cache, "close", Mock())
    monkeypatch.setattr(workers, "get_medialog", lambda _: "file")
    monkeypatch.setattr(workers, "log_download_progress", Mock())
    module = alt_download if drm else main_download
    cls = module.AltDownloadManager if drm else module.MainDownloadManager
    monkeypatch.setattr(module, "mark_media_as_downloaded", marked)
    monkeypatch.setattr(module.common_paths, "moveHelper", moved)
    monkeypatch.setattr(cls, "_after_download_script", after)
    monkeypatch.setattr(module, "send_chunk_msg", Mock())
    monkeypatch.setattr(cls, "_add_download_job_task", AsyncMock(return_value=1))
    monkeypatch.setattr(cls, "_remove_download_job_task", AsyncMock())
    if drm:
        monkeypatch.setattr(alt_download.placeholder, "Placeholders",
                            lambda *a: SimpleNamespace(init=AsyncMock(return_value=object())))
        monkeypatch.setattr(alt_download, "path_to_file_logger", Mock())

    async def transfer(self, *args, **kwargs):
        ele = args[2] if drm else args[1]
        part = tmp_path / f"{ele.id}.part"
        parts.append(part)
        holder = SimpleNamespace(tempfilepath=part)

        async def chunks():
            yield b"partial bytes"
            # Only after the first write: request from the UI/main thread.
            thread = threading.Thread(target=stop.request)
            thread.start()
            thread.join()
            await asyncio.sleep(30)

        response = SimpleNamespace(iter_chunked=lambda _: chunks())
        if drm:
            await self._download_fileobject_writer_streamer(ele, 100, response, holder)
        else:
            await self._download_fileobject_writer_streamer(response, ele, holder, holder, 100)
        pytest.fail("a stopped transfer reached finalisation")

    if drm:
        monkeypatch.setattr(cls, "_alt_download_downloader", transfer)
        async def drm_download(c, ele, model_id, username):
            # Real alt_download, including its semaphore and finalisation.
            async def track():
                return {"name": "track", "total": 100}
            ele.mpd_audio = track()
            ele.mpd_video = track()
            try:
                return await cls().alt_download(c, ele, username, model_id)
            finally:
                ele.mpd_audio.close()
                ele.mpd_video.close()
        monkeypatch.setattr(workers, "download", drm_download)
    else:
        monkeypatch.setattr(cls, "_main_download_downloader", transfer)

    async def go():
        return await asyncio.wait_for(download.process_dicts(
            "a creator", 1, media, [], on_result=lambda m, r: received.append((m.id, r))), 3)

    assert asyncio.run(go()) == (0, 0, 0, 0, 0)
    assert len(parts) == 1  # the second consumer was waiting for the semaphore
    assert parts[0].read_bytes() == b"partial bytes"
    assert received == [(3, "stopped")]
    assert download.common_globals.stopped == 1
    assert download.common_globals.skipped == 0
    assert all(m.download_unstarted for m in media[:3])
    marked.assert_not_called()
    moved.assert_not_called()
    after.assert_not_called()
    for m in media:
        m.mark_download_failed.assert_not_called()
        m.mark_download_succeeded.assert_not_called()


@pytest.mark.parametrize("menu", [True, False], ids=["menu", "cli"])
def test_first_interrupt_stops_then_returns_or_exits_130(monkeypatch, stop_signal, menu, caplog):
    stop = stop_signal
    final = Mock()
    monkeypatch.setattr(scraper, "final_action", final)

    def runner(self, menu=False):
        async def go():
            media = SimpleNamespace()
            with stop.transfer(media):
                stop.started(media)
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
                assert stop.requested.is_set()
                with pytest.raises(KeyboardInterrupt):
                    signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.sleep(0)
            raise stop.DownloadsStopped
        asyncio.run(go())

    monkeypatch.setattr(scraper.scraperManager, "_runner", runner)
    previous = signal.getsignal(signal.SIGINT)
    if menu:
        scraper.scraperManager().runner(menu=True)
    else:
        with pytest.raises(SystemExit) as exc:
            scraper.scraperManager().runner()
        assert exc.value.code == 130
    final.assert_called_once()
    assert signal.getsignal(signal.SIGINT) == previous
    assert "second Ctrl+C quits" in caplog.text


def test_interrupt_while_fetching_still_quits(stop_signal):
    with pytest.raises(KeyboardInterrupt):
        stop_signal.handle_interrupt(signal.SIGINT, None)


def test_stop_button_empties_queue_and_preserves_cart(monkeypatch, stop_signal):
    import ofscraper.commands.check as check
    row = {"index": 1, "download_cart": "[downloading]", "downloaded": False}
    q = queue.Queue()
    q.put(("1", row))
    monkeypatch.setattr(table, "row_queue", q)
    monkeypatch.setattr(check, "downloads_pending", lambda: True)
    app = table.InputApp()
    app.table_data = [row]
    monkeypatch.setattr(app, "update_cart_table", Mock())
    app.action_stop_downloads()
    assert stop_signal.requested.is_set()
    assert q.empty()
    assert row["download_cart"] == "[added]"
    assert not row["downloaded"]


def test_daemon_stop_ends_scheduler_and_marks_job_done(monkeypatch, stop_signal):
    from test.test_daemon_shutdown import _stub_daemon
    jobs = queue.Queue()
    def runner():
        stop_signal.request()
        raise SystemExit(130)
    _stub_daemon(monkeypatch, jobs, runner)
    clear = Mock()
    monkeypatch.setattr(scraper.schedule, "clear", clear)
    with pytest.raises(SystemExit) as exc:
        scraper.daemon_process()
    assert exc.value.code == 130
    assert jobs.unfinished_tasks == 0
    clear.assert_called_once()


@pytest.mark.parametrize("action", [
    "action_select_all_undownloaded", "action_select_page_undownloaded",
    "action_select_current_page", "action_select_all_filtered",
    "action_select_unique_all_filtered", "action_select_unique_current_page",
])
def test_stopped_rows_can_be_readded(action):
    from test.test_check_table_skipped import _FakeApp, _row
    row = _row(0, 1)
    row["download_cart"] = "[stopped]"
    app = _FakeApp([row])
    getattr(table.InputApp, action)(app)
    assert row["download_cart"] == "[added]"


@pytest.mark.parametrize("key", [True, False], ids=["binding", "button"])
def test_stop_control_keeps_table_open(monkeypatch, stop_signal, key):
    from test.test_check_table_sidebar_keys import _Settings, _drive
    import ofscraper.commands.check as check
    monkeypatch.setattr(table.settings, "get_settings", lambda: _Settings(db_sort="number", desc=False))
    monkeypatch.setattr(table.settings, "get_args", lambda: SimpleNamespace(text=False, text_only=False))
    monkeypatch.setattr(table.settings, "update_args", Mock())
    monkeypatch.setattr(table, "row_queue", queue.Queue())
    monkeypatch.setattr(check, "downloads_pending", lambda: True)

    async def steps(app, pilot):
        row = app.table_data[0]
        row["download_cart"] = "[added]"
        app.add_to_row_queue()
        assert not table.row_queue.empty()
        if key:
            app.query_one("#main_per_page_input").focus()
            await pilot.press("ctrl+x")
        else:
            await pilot.click("#stop_downloads")
        await pilot.pause()
        assert app.is_running
        assert row["download_cart"] == "[added]"
        assert table.row_queue.empty()
        assert stop_signal.requested.is_set()
    _drive(steps)


def test_stopped_file_can_be_clicked_and_sent_again(monkeypatch, stop_signal):
    from test.test_check_table_skipped import _FakeApp, _row, _click_cart_cell
    row = _row(0, 1)
    row["download_cart"] = "[stopped]"
    app = _FakeApp([row])
    monkeypatch.setattr(table, "row_queue", queue.Queue())
    assert _click_cart_cell(app, row) == ["[added]"]
    app.add_to_row_queue()
    assert table.row_queue.get_nowait() == ("0", row)


def test_stop_unwinds_actions_after_stats_before_script(monkeypatch, stop_signal):
    stats = Mock()
    script = Mock()
    monkeypatch.setattr(scraper.progress_utils, "setup_live", lambda *a, **k: nullcontext())
    monkeypatch.setattr(scraper.progress_updater, "activity", SimpleNamespace(update_task=Mock()))
    monkeypatch.setattr(scraper.settings, "get_settings", lambda: SimpleNamespace(actions=["download", "like"]))
    monkeypatch.setattr(scraper.manager, "Manager", SimpleNamespace(
        current_model_manager=SimpleNamespace(get_num_scrape_selected_models=lambda: 1),
        stats_manager=SimpleNamespace(update_and_print_stats=stats)))
    async def download_files(**kwargs):
        stop_signal.request()
    monkeypatch.setattr(scraper, "downloader", download_files)
    monkeypatch.setitem(scraper.ACTION_SCRIPTS, "download", script)
    media = [object()]
    collection = SimpleNamespace(get_media_for_processing=lambda: media,
                                 get_posts_to_like=lambda: [],
                                 get_posts_for_text_download=lambda: [])
    with pytest.raises(stop_signal.DownloadsStopped):
        asyncio.run(scraper.scraperManager()._execute_user_action(
            SimpleNamespace(id=1, name="a creator"), collection))
    stats.assert_called_once_with("a creator", "download", media)
    script.assert_not_called()


def test_decrypted_track_keeps_encrypted_part_until_merge(monkeypatch, tmp_path, stop_signal):
    from ofscraper.commands.scraper.actions.download.utils import keyhelpers
    part = tmp_path / "track.part"
    decrypted = tmp_path / "track.mp4"
    part.write_bytes(b"encrypted track")
    monkeypatch.setattr(keyhelpers.settings, "get_settings", lambda: SimpleNamespace(key_mode="manual"))
    real_getattr = keyhelpers.of_env.getattr
    monkeypatch.setattr(keyhelpers.of_env, "getattr", lambda key, default=None:
                        False if key == "USE_WIV_CACHE_KEY" else real_getattr(key, default))
    monkeypatch.setattr(keyhelpers, "key_helper_manual", AsyncMock(return_value="test value"))
    monkeypatch.setattr(keyhelpers, "get_ffmpeg_key", lambda _: "test value")
    monkeypatch.setattr(keyhelpers, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(keyhelpers, "strip_pssh", Mock(return_value=0))
    monkeypatch.setattr(keyhelpers.cache, "set", Mock())
    async def decrypt(*args, **kwargs):
        decrypted.write_bytes(b"decrypted track")
        return SimpleNamespace()
    monkeypatch.setattr(keyhelpers, "async_run", decrypt)
    item = {"path": part, "ext": "mp4", "pssh": None}
    async def go():
        with ThreadPoolExecutor(1) as pool:
            monkeypatch.setattr(keyhelpers.common_globals, "thread", pool, raising=False)
            await keyhelpers.un_encrypt(item, None, SimpleNamespace(id=1, post_id=1, license="test"), input_=Mock())
            stop_signal.request()
    asyncio.run(go())
    assert part.read_bytes() == b"encrypted track"
    assert item["path"] == decrypted


@pytest.mark.parametrize(
    "stopped, key_failure", [(False, False), (True, False), (False, True)],
    ids=["integrity-failure", "stop", "key-failure"],
)
def test_drm_merge_failure_cleans_parts_unless_stopped(
    monkeypatch, tmp_path, stop_signal, stopped, key_failure
):
    cls = alt_download.AltDownloadManager
    parts = [tmp_path / f"{name}.part" for name in ("audio", "video")]
    tracks = [{"path": part, "total": 10} for part in parts]
    for part in parts:
        part.write_bytes(b"encrypted track")
    holder = SimpleNamespace(trunicated_filepath=tmp_path / "final.mp4")
    merged = tmp_path / "merged.mp4"
    monkeypatch.setattr(alt_download.common_globals, "sem", asyncio.Semaphore(1), raising=False)
    monkeypatch.setattr(alt_download.common_globals, "log", Mock())
    monkeypatch.setattr(alt_download.placeholder, "Placeholders",
                        lambda *a: SimpleNamespace(init=AsyncMock(return_value=holder)))
    monkeypatch.setattr(alt_download.placeholder, "tempFilePlaceholder",
                        lambda *a: SimpleNamespace(init=AsyncMock(
                            return_value=SimpleNamespace(tempfilepath=merged))))
    monkeypatch.setattr(alt_download, "path_to_file_logger", Mock())
    monkeypatch.setattr(alt_download, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(alt_download, "verify_media_integrity", Mock(return_value=False))
    monkeypatch.setattr(cls, "_alt_download_downloader", AsyncMock(side_effect=lambda item, *a, **k: item))
    monkeypatch.setattr(cls, "_media_item_post_process_alt", AsyncMock(return_value=None))

    async def decrypt(c, audio, video, ele):
        if key_failure:
            raise RuntimeError("DRM key acquisition failed")
        for track in (audio, video):
            track["path"] = track["path"].with_suffix(".mp4")
            track["path"].write_bytes(b"decrypted track")

    async def merge(*args, **kwargs):
        merged.write_bytes(b"invalid merged media")
        if stopped:
            stop_signal.request()
            stop_signal.check()
        return SimpleNamespace(stderr=b"")

    monkeypatch.setattr(cls, "_media_item_keys_alt", AsyncMock(side_effect=decrypt))
    monkeypatch.setattr(alt_download, "async_run", merge)

    async def track(item):
        return item

    async def go():
        ele = SimpleNamespace(id=1, post_id=1, mediatype="videos", duration=1,
                              url=None, mpd="https://example.invalid/manifest.mpd",
                              add_size=Mock(), mpd_audio=track(tracks[0]),
                              mpd_video=track(tracks[1]))
        error = asyncio.CancelledError if stopped else Exception
        match = None if stopped else "Merged DRM media failed integrity check"
        if key_failure:
            match = "DRM key acquisition failed"
        with pytest.raises(error, match=match):
            await cls().alt_download(None, ele, "a creator", 1)

    asyncio.run(go())
    assert all(part.exists() == (stopped or key_failure) for part in parts)
    if stopped or key_failure:
        assert all(part.read_bytes() == b"encrypted track" for part in parts)
        if key_failure:
            assert not stop_signal.requested.is_set()
            alt_download.verify_media_integrity.assert_not_called()
    else:
        alt_download.verify_media_integrity.assert_called_once_with(merged, 1)


def test_stop_preserves_parts_during_batch_cleanup(monkeypatch, tmp_path, stop_signal):
    import ofscraper.utils.paths.paths as paths
    part = tmp_path / "file.part"
    part.write_bytes(b"partial")
    monkeypatch.setattr(paths.of_env, "getattr", lambda *a: True)
    monkeypatch.setattr(paths.settings, "get_settings", lambda: SimpleNamespace(auto_resume=False))
    monkeypatch.setattr(paths.data, "get_TempDir", lambda: tmp_path)
    stop_signal.request()
    paths.temp_cleanup()
    assert part.read_bytes() == b"partial"


def test_stop_during_integrity_check_keeps_part(monkeypatch, tmp_path, stop_signal):
    part = tmp_path / "file.part"
    part.write_bytes(b"partial")
    holder = SimpleNamespace(trunicated_filepath=tmp_path / "file.mp4")
    monkeypatch.setattr(main_download.MainDownloadManager, "_size_checker", AsyncMock())
    monkeypatch.setattr(main_download.settings, "get_settings", lambda: SimpleNamespace(verify_all_integrity=True))
    monkeypatch.setattr(main_download.common_globals, "log", Mock())
    def verify(*args):
        stop_signal.request()
        return False
    monkeypatch.setattr(main_download, "verify_media_integrity", verify)
    async def filename():
        return "file.mp4"
    async def go():
        ele = SimpleNamespace(id=1, post_id=1, mediatype="videos", duration=1,
                              final_filename=filename())
        with pytest.raises(asyncio.CancelledError):
            await main_download.MainDownloadManager()._handle_result_main(
                (100, part, holder), ele, "a creator", 1)
    asyncio.run(go())
    assert part.read_bytes() == b"partial"
    assert not holder.trunicated_filepath.exists()


def test_next_run_clears_stop_signal(stop_signal):
    stop_signal.request()
    with stop_signal.interrupt_handler():
        assert not stop_signal.requested.is_set()


def test_cli_stop_closes_resources_and_preserves_exit_code(monkeypatch):
    import ofscraper.main.open.run as entry
    monkeypatch.setattr(entry, "start_manager", Mock(side_effect=SystemExit(130)))
    shutdown = Mock()
    monkeypatch.setattr(entry.exit_manager, "shutdown", shutdown)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 130
    shutdown.assert_called_once()
