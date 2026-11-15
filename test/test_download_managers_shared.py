"""The normal and DRM downloaders share their part writer, their cache of
reply data and the reading of that cache. These pin what each one does, so
the shared code keeps both behaviours: the arguments each passes, the cache
key each uses and what each does with a saved reply."""

import asyncio
import contextvars
import logging
from types import SimpleNamespace

import aiohttp
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.settings as settings


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            auto_resume=True, download_limit=0, command="download"
        ),
    )
    monkeypatch.setattr(common_globals, "log", logging.getLogger("test"), raising=False)
    monkeypatch.setattr(common_globals, "thread", None, raising=False)
    for name in ("attempt", "attempt2"):
        monkeypatch.setattr(
            common_globals, name, contextvars.ContextVar(name, default=0), raising=False
        )
    monkeypatch.setattr(md.common_logs, "get_medialog", lambda ele: "")
    monkeypatch.setattr(md.common_logs, "path_to_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(dm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)


ELE = SimpleNamespace(id=1, post_id=2, username="u", filename="f", url="x")


def _manager(drm):
    """A manager that records its progress task calls."""
    mgr = (ad.AltDownloadManager if drm else md.MainDownloadManager)()
    calls = {"add": [], "remove": []}

    async def add(*args, **kwargs):
        calls["add"].append((args, kwargs))
        return "task"

    async def remove(task, ele):
        calls["remove"].append(task)

    mgr._add_download_job_task = add
    mgr._remove_download_job_task = remove
    return mgr, calls


def _reply(chunks, error=None):
    async def gen():
        for chunk in chunks:
            yield chunk
        if error:
            raise error

    return SimpleNamespace(iter_chunked=lambda size: gen())


def _write(mgr, drm, reply, holder, total=10, resume_size=0, on_first_chunk=None):
    if drm:
        coro = mgr._download_fileobject_writer_streamer(
            ELE, total, reply, holder, resume_size, on_first_chunk
        )
    else:
        coro = mgr._download_fileobject_writer_streamer(
            reply, ELE, holder, holder, total, resume_size, on_first_chunk
        )
    return asyncio.run(coro)


DRM = pytest.mark.parametrize("drm", [False, True], ids=["normal", "drm"])


@DRM
@pytest.mark.parametrize("resume_size", [0, 3])
def test_writer_appends_on_resume_and_replaces_otherwise(
    tmp_path, monkeypatch, drm, resume_size
):
    part = tmp_path / "f.part"
    part.write_bytes(b"old")
    holder = SimpleNamespace(tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4")
    events = []
    module = ad if drm else md
    monkeypatch.setattr(
        # the fourth argument is the manager's log
        module, "send_chunk_msg", lambda ele, total, h, log: events.append((ele, total, h))
    )

    async def first():
        events.append("first")

    mgr, calls = _manager(drm)
    written = _write(mgr, drm, _reply([b"ab", b"cd"]), holder, 10, resume_size, first)
    assert written == 4
    assert part.read_bytes() == (b"oldabcd" if resume_size else b"abcd")
    # on_first_chunk runs once, after the first chunk is written and before
    # its progress message
    assert events == ["first", (ELE, 10, holder), (ELE, 10, holder)]
    if drm:
        assert calls["add"] == [((ELE, 10, holder), {})]
    else:
        assert calls["add"] == [
            ((ELE,), {"total": 10, "tempholderObj": holder, "placeholderObj": holder})
        ]
    assert calls["remove"] == ["task"]


@DRM
def test_writer_with_no_data_leaves_the_part(tmp_path, drm):
    part = tmp_path / "f.part"
    part.write_bytes(b"old")
    holder = SimpleNamespace(tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4")
    mgr, calls = _manager(drm)
    assert _write(mgr, drm, _reply([]), holder) == 0
    assert part.read_bytes() == b"old"
    assert calls["remove"] == ["task"]


@DRM
@pytest.mark.parametrize(
    "error", [asyncio.TimeoutError(), aiohttp.ServerTimeoutError()], ids=["asyncio", "aiohttp"]
)
def test_writer_turns_a_read_timeout_into_a_retryable_error(
    tmp_path, monkeypatch, drm, error
):
    monkeypatch.setattr(ad if drm else md, "send_chunk_msg", lambda *a: None)
    part = tmp_path / "f.part"
    holder = SimpleNamespace(tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4")
    mgr, calls = _manager(drm)
    with pytest.raises(Exception) as raised:
        _write(mgr, drm, _reply([b"ab"], error), holder)
    assert type(raised.value) is Exception
    assert str(raised.value) == "Chunk download timed out"
    assert part.read_bytes() == b"ab"
    assert calls["remove"] == ["task"]


@DRM
def test_writer_reraises_other_errors(tmp_path, monkeypatch, drm):
    monkeypatch.setattr(ad if drm else md, "send_chunk_msg", lambda *a: None)
    holder = SimpleNamespace(
        tempfilepath=tmp_path / "f.part", trunicated_filepath=tmp_path / "f.mp4"
    )
    mgr, calls = _manager(drm)
    error = ValueError("boom")
    with pytest.raises(ValueError) as raised:
        _write(mgr, drm, _reply([b"ab"], error), holder)
    assert raised.value is error
    assert calls["remove"] == ["task"]


def test_progress_task_labels(tmp_path, monkeypatch):
    added = []
    monkeypatch.setattr(
        dm.progress_updater,
        "download",
        SimpleNamespace(add_job_task=lambda *a, **k: added.append((a, k)) or "t"),
    )
    temp = SimpleNamespace(tempfilepath=tmp_path / "f.part")
    final = SimpleNamespace(trunicated_filepath=tmp_path / "f.mp4")
    asyncio.run(
        dm.DownloadManager._add_download_job_task(
            md.MainDownloadManager(), ELE, total=5, placeholderObj=final, tempholderObj=temp
        )
    )
    asyncio.run(ad.AltDownloadManager()._add_download_job_task(ELE, 6, temp))
    # the normal file is labelled with its final name; a DRM track with its part
    assert added == [
        ((f"{final.trunicated_filepath}\n",), {"total": 5, "file": temp.tempfilepath}),
        ((f"{temp.tempfilepath}\n",), {"total": 6}),
    ]


@pytest.fixture
def fake_cache(monkeypatch):
    store = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value, *a, **k: store.__setitem__(key, value))
    return store


def test_cache_keys(fake_cache):
    item = {"name": "track"}

    async def go():
        main, alt = md.MainDownloadManager(), ad.AltDownloadManager()
        await main._set_data(ELE, {"m": 1})
        await alt._set_data(ELE, item, {"a": 1})
        return await main._get_data(ELE), await alt._get_data(ELE, item)

    assert asyncio.run(go()) == ({"m": 1}, {"a": 1})
    assert fake_cache == {"1_u_headers": {"m": 1}, "track_1_u_headers": {"a": 1}}


def _holder(tmp_path, size):
    part = tmp_path / "f.part"
    if size is not None:
        part.write_bytes(b"x" * size)
    return SimpleNamespace(tempfilepath=part)


def _resume(drm, data, holder, monkeypatch):
    mgr = (ad.AltDownloadManager if drm else md.MainDownloadManager)()

    async def no_skip(*a):
        return None

    mgr._check_forced_skip = no_skip
    if drm:
        item = {"name": "track", "type": "video"}
        return asyncio.run(mgr._resume_data_handler_alt(data, item, ELE, holder))

    class _Placeholders:
        def __init__(self, ele, content_type):
            self.content_type = content_type

        async def init(self):
            return self

    monkeypatch.setattr(md.placeholder, "Placeholders", _Placeholders)
    return asyncio.run(mgr._resume_data_handler_main(data, ELE, holder))


@DRM
def test_resume_from_a_finished_part(tmp_path, monkeypatch, fake_cache, drm):
    holder = _holder(tmp_path, 10)
    data = {"content-total": 10, "content-type": "video/mp4", "validator": "v"}
    result = _resume(drm, data, holder, monkeypatch)
    if drm:
        assert result == ({"name": "track", "type": "video", "total": 10, "validator": "v"}, True)
    else:
        total, placeholderObj, check = result
        assert (total, placeholderObj.content_type, check) == (10, "mp4", True)
    assert holder.tempfilepath.read_bytes() == b"x" * 10


@DRM
def test_resume_from_a_part_larger_than_the_file(tmp_path, monkeypatch, fake_cache, drm):
    holder = _holder(tmp_path, 12)
    data = {"content-total": 10, "content-type": "video/mp4", "validator": None}
    result = _resume(drm, data, holder, monkeypatch)
    assert not holder.tempfilepath.exists()
    if drm:
        assert result == (
            {"name": "track", "type": "video", "total": 10, "validator": None},
            False,
        )
    else:
        assert result[0] == 10 and result[2] is None


@DRM
def test_resume_with_no_saved_size(tmp_path, monkeypatch, fake_cache, drm):
    fake_cache["track_1_u_headers"] = fake_cache["1_u_headers"] = {"old": 1}
    holder = _holder(tmp_path, 4)
    data = {"content-total": None, "content-type": "video/mp4"}
    result = _resume(drm, data, holder, monkeypatch)
    # there's nothing to check the part against, so it's removed
    assert not holder.tempfilepath.exists()
    if drm:
        # the DRM downloader also clears the saved reply; the normal one keeps it
        assert result == (
            {"name": "track", "type": "video", "total": None, "validator": None},
            False,
        )
        assert fake_cache == {"track_1_u_headers": None, "1_u_headers": {"old": 1}}
    else:
        assert result[0] is None and result[2] is None
        assert fake_cache == {"track_1_u_headers": {"old": 1}, "1_u_headers": {"old": 1}}
