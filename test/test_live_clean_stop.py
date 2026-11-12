"""Clean recording stops use fake processes only (#442)."""

import asyncio
import json
import pathlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ofscraper.commands.scraper import scraper
from ofscraper.commands.scraper.actions.download import stop as download_stop
from ofscraper.sites.fansly import live


class FakeProcess:
    def __init__(self, exits_on_q=True):
        self.returncode = None
        self.exited = asyncio.Event()
        self.calls = []
        self.exits_on_q = exits_on_q
        self.stdin = SimpleNamespace(write=self.write, drain=self.drain)

    def write(self, data):
        self.calls.append(data)
        if self.exits_on_q:
            self.finish(0)

    async def drain(self):
        pass

    def finish(self, code):
        self.returncode = code
        self.exited.set()

    def terminate(self):
        self.calls.append("terminate")
        self.finish(-1)

    def kill(self):
        self.calls.append("kill")
        self.finish(-1)

    async def wait(self):
        await self.exited.wait()
        return self.returncode

    async def communicate(self):
        await self.wait()
        return None, b""


@pytest.mark.parametrize("timeout", [False, True])
def test_stop_sends_q_and_only_kills_after_15_seconds(monkeypatch, timeout):
    async def scenario():
        proc = FakeProcess(exits_on_q=not timeout)
        inputs = []

        async def spawn(*cmd, **kwargs):
            inputs.append(kwargs["stdin"])
            return proc

        async def wait_for(awaitable, *, timeout):
            assert timeout == 15
            assert proc.calls == [b"q\n"]
            if not proc.exits_on_q:
                proc.calls.append("15 seconds elapsed")
                awaitable.cancel()  # cancelling the shield leaves communicate running
                raise asyncio.TimeoutError
            return await awaitable

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        monkeypatch.setattr(asyncio, "wait_for", wait_for)
        stop = asyncio.Event()
        stop.set()
        code = await live.run_ffmpeg(["ffmpeg"], stop)
        assert code == (-1 if timeout else 0)
        assert proc.calls == ([b"q\n", "15 seconds elapsed", "kill"] if timeout else [b"q\n"])
        assert inputs == [asyncio.subprocess.PIPE]

    asyncio.run(scenario())
    assert "-nostdin" not in live.ffmpeg_command("ffmpeg", "https://example.invalid/live", pathlib.Path("live.mp4"))


def test_stopped_recording_keeps_all_parts_and_sidecar(tmp_path):
    async def scenario():
        stop = asyncio.Event()

        async def channel():
            return {"live": True, "playbackUrl": "https://example.invalid/live"}

        async def playlist(url):
            return "#EXTM3U\n#EXTINF:2,\nsegment.ts\n"

        async def record(cmd, stop):
            pathlib.Path(cmd[-1]).write_bytes(b"finished recording")
            if len(rec.parts) == 1:
                stop.set()
            return 0

        rec = live.LiveRecorder({"username": "a creator", "startedAt": 1760000000},
                                tmp_path, channel, playlist, ffmpeg_runner=record, backoff=(0, 0))
        sidecar = await rec.run(stop)
        assert len(rec.parts) == 2
        assert all(p.read_bytes() == b"finished recording" for p in rec.parts)
        assert rec.parts[1].stem.endswith("_part2")
        assert sidecar["parts"] == [p.name for p in rec.parts]
        assert sidecar["endReason"] == "stopped"
        assert json.loads(live.sidecar_path(rec.base).read_text(encoding="utf-8")) == sidecar

    asyncio.run(scenario())


@pytest.mark.parametrize("menu", [True, False])
def test_first_foreground_interrupt_returns_to_menu_or_exits_130(monkeypatch, menu):
    thread = Mock()
    thread.is_alive.side_effect = KeyboardInterrupt
    monkeypatch.setattr(live, "LiveThread", Mock(return_value=thread))
    if menu:
        assert live.run_blocking(False, menu=True) is True
    else:
        with pytest.raises(SystemExit) as exc:
            live.run_blocking(False)
        assert exc.value.code == 130
    thread.stop.assert_called_once_with()


def test_second_interrupt_force_stops_and_quits(monkeypatch, caplog):
    thread = live.LiveThread(False)
    monkeypatch.setattr(thread, "_stop_recordings", Mock(side_effect=KeyboardInterrupt))
    force = Mock()
    monkeypatch.setattr(thread, "force_stop", force)
    with pytest.raises(KeyboardInterrupt):
        thread.stop()
    force.assert_called_once_with()
    assert "second Ctrl+C quits" in caplog.text


def test_foreground_interrupt_waits_for_loop_cleanup_even_if_join_is_interrupted(monkeypatch):
    processes = []

    async def spawn(*args, **kwargs):
        proc = FakeProcess()
        processes.append(proc)
        return proc

    async def runner(watch, stop):
        await live.run_ffmpeg(["ffmpeg"], stop)

    def interrupted_join(self, timeout=None):
        # An interrupted Thread.join can mark the thread stopped on Windows.
        # Subsequent joins then return before the recording has finished.
        if not getattr(self, "interrupted", False):
            self.interrupted = True
            raise KeyboardInterrupt

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(live.LiveThread, "join", interrupted_join)
    assert live.run_blocking(False, runner=runner, menu=True) is True
    assert processes[0].calls == [b"q\n"]
    assert processes[0].returncode == 0


@pytest.mark.parametrize("watcher", [False, True])
def test_force_stop_kills_ffmpeg_without_waiting_for_q(monkeypatch, watcher):
    started = live.threading.Event()
    processes = []

    async def spawn(*args, **kwargs):
        proc = FakeProcess(exits_on_q=False)
        processes.append(proc)
        if len(processes) == (2 if watcher else 1):
            started.set()
        return proc

    async def runner(watch, stop):
        if watcher:
            async def online():
                return [{"accountId": "1"}, {"accountId": "2"}]

            async def record(stream, stop):
                await live.run_ffmpeg(["ffmpeg"], stop)

            await live.LiveWatcher(online, record, once=True).run(stop)
        else:
            await live.run_ffmpeg(["ffmpeg"], stop)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    thread = live.LiveThread(False, runner)
    thread.start()
    try:
        assert started.wait(5)
    finally:
        thread.force_stop()
    assert not thread.is_alive()
    assert all(proc.calls == ["kill"] for proc in processes)


def test_menu_interrupt_skips_scraping_after_recording(monkeypatch):
    monkeypatch.setattr(scraper, "check_auth", Mock())
    monkeypatch.setattr(live, "once_enabled", lambda: True)
    recording = Mock(return_value=True)
    monkeypatch.setattr(live, "run_blocking", recording)
    final = Mock()
    monkeypatch.setattr(scraper, "final_action", final)
    monkeypatch.setattr(scraper, "scrape_context_manager", Mock(side_effect=AssertionError("continued scraping")))
    scraper.scraperManager().runner(menu=True)
    recording.assert_called_once_with(watch=False, menu=True)
    final.assert_called_once_with()


@pytest.mark.parametrize("second", [False, True])
def test_daemon_interrupt_stops_recordings_or_force_quits(monkeypatch, second):
    from test.test_daemon_shutdown import _stub_daemon, InterruptWhenIdle

    download_stop.clear()
    _stub_daemon(monkeypatch, InterruptWhenIdle(), lambda: None)
    thread = Mock()
    monkeypatch.setattr(live, "watch_enabled", lambda: True)
    monkeypatch.setattr(live, "start_watch_thread", lambda: thread)
    if second:
        download_stop.request()
    try:
        with pytest.raises(KeyboardInterrupt if second else SystemExit) as exc:
            scraper.daemon_process()
        if second:
            thread.force_stop.assert_called_once_with()
            thread.stop.assert_not_called()
        else:
            assert exc.value.code == 130
            thread.stop.assert_called_once_with()
    finally:
        download_stop.clear()
