import logging
import logging.handlers
import queue
import threading
from types import SimpleNamespace

import diskcache

import ofscraper.utils.cache.cache as cache_mod
import ofscraper.utils.logs.close as close_mod
import ofscraper.utils.logs.other as other_logs


def test_cache_get_on_worker_thread_closes_its_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod.settings, "get_settings", lambda: SimpleNamespace(cached_disabled=False))
    monkeypatch.setattr(cache_mod.common_paths, "getcachepath", lambda: str(tmp_path))
    monkeypatch.setattr(cache_mod.data, "get_cache_mode", lambda: diskcache.Disk)
    monkeypatch.setattr(cache_mod, "cache", None)
    cache_mod.set("k", "v")
    left_open = []

    def worker():
        assert cache_mod.get("k") == "v"
        left_open.append(getattr(cache_mod.cache._local, "con", None))

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert left_open == [None]
    cache_mod.close()


def test_graceful_close_closes_log_files(tmp_path, monkeypatch):
    fh = logging.FileHandler(tmp_path / "x.log", encoding="utf-8")
    q = queue.Queue()
    listener = logging.handlers.QueueListener(q, fh)
    listener.start()
    monkeypatch.setattr(other_logs, "log_queue_listener", listener, raising=False)
    shared = logging.getLogger("shared")
    qh = logging.handlers.QueueHandler(q)
    shared.addHandler(qh)
    close_mod.gracefulClose()
    assert fh.stream is None  # FileHandler.close() drops the stream
    assert shared.handlers == []
