"""A file skipped by a size limit is counted as skipped and isn't saved as
downloaded (#319).

A size limit sets the item's mediatype to "Forced_skipped", which
Media.mediatype read back as "Forced_skippeds". The downloaders' check for a
size skip never matched, so the item was saved as downloaded (a later run
without the limit didn't fetch it), and run.py's counters didn't match it
either. Each test runs run.py's consumer with the real Media and download
managers, against a local server (or a fake Fansly session and ffmpeg) and a
real SQLite database in a temporary folder, then runs it again without the
limit.
"""

import asyncio
import contextlib
import copy
import json
import logging
import pathlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from aiohttp import web

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.fansly_stream_download as stream_mod
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.run as run_mod
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.db.operations as operations
import ofscraper.filters.media.filters as filters
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import video as fansly_video

MODEL_ID = 12345
USERNAME = "a-creator"
BODY = bytes(i % 251 for i in range(50_000))
STREAM_SIZE = 2048
FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "fansly"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/140.0"

# (size_min, size_max) that skip a file of `size` bytes, and none
LIMITS = {
    "under -sm": lambda size: (size + 1, 0),
    "over -sx": lambda size: (0, size - 1),
}


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


async def _noop(*a, **k):
    return None


@pytest.fixture
def env(monkeypatch, tmp_path):
    real = settings.get_settings()
    stub = SimpleNamespace(**{
        **dict(real), "site": "onlyfans", "size_max": 0, "size_min": 0,
        "auto_resume": True, "download_limit": 0, "ssl_verify": "false",
        "verify_all_integrity": False, "force_all": False, "force_model_unique": False,
        "skip_download_script": None, "hash": "xxh128", "proxy": None,
        "cached_disabled": True, "download_sems": 2,
    })
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)

    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    async def create():
        # inside a running loop: called outside one, it opens a loop it never closes
        await operations.create_tables(db_path=db)

    asyncio.run(create())

    out_dir, temp_dir = tmp_path / "out", tmp_path / "temp"
    out_dir.mkdir()
    temp_dir.mkdir()

    class FakePlaceholders:
        def __init__(self, ele, ext):
            self.filename = f"{ele.filename}.{ext}"
            self.filepath = self.trunicated_filepath = out_dir / self.filename

        async def init(self):
            return self

    class FakeTemp:
        def __init__(self, ele, name):
            self.tempfilepath = temp_dir / name

        async def init(self):
            return self

    monkeypatch.setattr(placeholder, "Placeholders", FakePlaceholders)
    monkeypatch.setattr(placeholder, "tempFilePlaceholder", FakeTemp)

    # the download globals, without the shared logger or the live display
    common_globals.set_up_contexvars()
    pool = ThreadPoolExecutor(max_workers=4)
    for name, value in {
        "thread": pool, "log": _Log(), "dirSet": set(), "localDirSet": set(),
        "fileHashes": {}, "total_bytes": 0,
    }.items():
        monkeypatch.setattr(common_globals, name, value, raising=False)
    monkeypatch.setattr(
        run_mod, "progress_updater",
        SimpleNamespace(download=SimpleNamespace(update_overall_task=lambda *a, **k: None)),
    )
    monkeypatch.setattr(run_mod, "asyncio", SimpleNamespace(sleep=_noop))
    for name in ("_add_download_job_task", "_remove_download_job_task", "_total_change_helper"):
        monkeypatch.setattr(dm.DownloadManager, name, _noop)
    monkeypatch.setattr(md, "send_chunk_msg", lambda *a, **k: None)
    # the saved reply headers, kept between runs as the cache keeps them
    cached = {}

    async def get_data(self, ele):
        return cached.get(ele.id)

    async def set_data(self, ele, data):
        cached[ele.id] = data

    monkeypatch.setattr(md.MainDownloadManager, "_get_data", get_data)
    monkeypatch.setattr(md.MainDownloadManager, "_set_data", set_data)
    for module in (md, stream_mod):
        monkeypatch.setattr(module, "set_profile_cache", _noop)
    monkeypatch.setattr(dm, "after_download_script", _noop)
    monkeypatch.setattr(dm.system, "check_free_size", lambda: True)
    monkeypatch.setattr(filters.separate, "seperate_avatars", lambda m: m)
    yield SimpleNamespace(stub=stub, db=db, out=out_dir, temp=temp_dir)
    pool.shutdown(wait=True)


COUNTERS = ("photo_count", "video_count", "audio_count", "skipped", "forced_skipped")


async def run_async(env, items, c, size_min=0, size_max=0):
    """One download run of `items` through run.py's consumer, as the app runs
    it: only the items the database doesn't list as downloaded, after the
    scrape has saved them. Returns (the counters, the items downloaded)."""
    env.stub.size_min, env.stub.size_max = size_min, size_max
    for name in COUNTERS + ("total_bytes_downloaded",):
        setattr(common_globals, name, 0)
    common_globals.sem = asyncio.Semaphore(2)
    await batch_mediainsert(items, model_id=MODEL_ID, username=USERNAME)
    todo = filters.previous_download_filter(items, username=USERNAME, model_id=MODEL_ID)
    aws = [(c, ele, MODEL_ID, USERNAME) for ele in todo]
    await run_mod.consumer(aws, None, todo, asyncio.Lock())
    return {name: getattr(common_globals, name) for name in COUNTERS}, todo


def run_once(env, items, c, size_min=0, size_max=0):
    return asyncio.run(run_async(env, items, c, size_min, size_max))


def downloaded(env, media_id):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        return conn.execute(
            "SELECT downloaded FROM medias WHERE media_id = ?", [media_id]
        ).fetchone()[0]


def counts(**nonzero):
    base = dict(photo_count=0, video_count=0, audio_count=0, skipped=0, forced_skipped=0)
    return {**base, **nonzero}


# ------------------------------------------------------------- normal downloader

async def _chunked(request):
    """The file sent chunked, without its size (no Content-Length)."""
    resp = web.StreamResponse(headers={"Content-Type": "image/jpeg"})
    resp.enable_chunked_encoding()
    await resp.prepare(request)
    for i in range(0, len(BODY), 8192):
        await resp.write(BODY[i : i + 8192])
    await resp.write_eof()
    return resp


class Server:
    """A local server for the file, kept up for both runs. With chunked it
    sends the file chunked, without its size (no Content-Length)."""

    def __init__(self, chunked=False):
        self.chunked = chunked

    async def __aenter__(self):
        async def handler(request):
            if request.match_info["name"].startswith("gone"):
                return web.Response(status=404)
            return web.Response(body=BODY, content_type="image/jpeg")

        app = web.Application()
        app.router.add_get("/{name}", _chunked if self.chunked else handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        return self

    async def __aexit__(self, *exc):
        await self.runner.cleanup()


def photo(base, name="abc123def"):
    post = Post(
        {"id": 1, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        MODEL_ID, USERNAME, responsetype="timeline",
    )
    return Media(
        {"id": 7, "type": "photo", "canView": True,
         "files": {"full": {"url": f"{base}/{name}.jpg"}}},
        0, post,
    )


def normal_runs(env, *limits, chunked=False):
    """Run the normal downloader once per (size_min, size_max) in `limits`,
    each run with a new Media as a new scrape makes. chunked: the server
    sends the file without its size."""
    results = []

    async def runs():
        async with Server(chunked) as srv:
            async with sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                for size_min, size_max in limits:
                    counted, todo = await run_async(
                        env, [photo(srv.base)], c, size_min, size_max
                    )
                    results.append(SimpleNamespace(
                        counted=counted, todo=[ele.id for ele in todo],
                        downloaded=downloaded(env, 7), files=files(env),
                    ))

    asyncio.run(runs())
    return results


def files(env):
    return [p.read_bytes() for p in sorted(env.out.iterdir())] + sorted(
        p.name for p in env.temp.iterdir()
    )


# a reply that gives the file's size, and one that doesn't (chunked, no
# Content-Length), whose size is known only once it's written (#336)
REPLIES = pytest.mark.parametrize("chunked", [False, True], ids=["sized", "no size"])


@REPLIES
@pytest.mark.parametrize("limit", list(LIMITS), ids=list(LIMITS))
def test_size_skip_is_counted_and_downloaded_later(env, limit, chunked):
    skip, later = normal_runs(env, LIMITS[limit](len(BODY)), (0, 0), chunked=chunked)
    assert skip.counted == counts(forced_skipped=1)
    assert not skip.downloaded
    assert skip.files == []
    # the next run without the limit still has the file to do, and fetches it
    assert later.todo == [7]
    assert later.counted == counts(photo_count=1)
    assert later.downloaded == 1
    assert later.files == [BODY]


@REPLIES
def test_no_limits_unchanged(env, chunked):
    first, second = normal_runs(env, (0, 0), (0, 0), chunked=chunked)
    assert first.todo == [7]
    assert first.counted == counts(photo_count=1)
    assert first.downloaded == 1
    assert first.files == [BODY]
    assert second.todo == [] and second.counted == counts()


@REPLIES
def test_limit_the_file_is_inside_downloads_it(env, chunked):
    (first,) = normal_runs(env, (len(BODY) - 1, len(BODY) + 1), chunked=chunked)
    assert first.counted == counts(photo_count=1)
    assert first.downloaded == 1
    assert first.files == [BODY]


@REPLIES
def test_skip_download_script_still_saves_the_item_as_done(env, monkeypatch, chunked):
    # unchanged: a skip by the skip_download_script is a lasting choice; the
    # item is saved as downloaded (with no file) and counted under its type.
    # It's asked once, with the file's real size, whether the reply gave it
    asked = []

    async def skip(total, ele):
        asked.append(total)
        return True

    monkeypatch.setattr(dm, "skip_download_script", skip)
    first, second = normal_runs(env, (0, 0), (0, 0), chunked=chunked)
    assert asked == [len(BODY)]
    assert first.counted == counts(photo_count=1)
    assert first.downloaded == 1
    assert first.files == []
    assert second.todo == [] and second.counted == counts()


# ------------------------------------------------------------- Fansly stream

def fansly_item():
    data = json.loads((FIXTURES / "video_4k_account_media.json").read_text(encoding="utf-8"))
    account_media = copy.deepcopy(data["response"][0])
    raw = account_media["media"]
    direct = next(
        loc["location"] for loc in raw.get("locations") or [] if str(loc["locationId"]) == "1"
    )
    post = Post(
        {"id": 100000000000000005, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        MODEL_ID, USERNAME, responsetype="timeline",
    )
    ele = Media({
        "id": int(raw["id"]), "type": "video", "canView": True,
        "files": {"full": {"url": direct}},
        "fansly": {"accountMediaId": account_media["id"], "mediaId": raw["id"],
                   "isPreview": False, "media": raw},
    }, 0, post)
    hls = next(v for v in raw["variants"] if v["mimetype"] == fansly_video.HLS_MIME)
    return ele, hls["locations"][0]["location"]


class FakeResponse:
    def __init__(self, body, status=200):
        self.ok = status < 400
        self.status = status
        self._body = body

    async def text_(self):
        return self._body


class FakeSession:
    def __init__(self, bodies):
        self.bodies = bodies

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        yield FakeResponse(self.bodies.get(url, ""), 200 if url in self.bodies else 404)


@pytest.fixture
def fansly(env, monkeypatch):
    env.stub.site = "fansly"
    monkeypatch.setattr(fansly_auth, "read_auth", lambda *a, **k: {"user_agent": UA})
    runs = []

    async def fake_ffmpeg(self, url, temp, cookies, audio_url=None, timeout=None):
        runs.append(url)
        temp.write_bytes(b"\0" * STREAM_SIZE)

    async def no_main_download(self, *a, **k):
        raise AssertionError("normal downloader used for a stream")

    monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, "_run_ffmpeg", fake_ffmpeg)
    for name in ("_integrity_check", "_check_complete"):
        monkeypatch.setattr(stream_mod.FanslyStreamDownloadManager, name, _noop)
    monkeypatch.setattr(run_mod.MainDownloadManager, "main_download", no_main_download)
    ele, hls_url = fansly_item()
    playlist = (FIXTURES / "media_playlist.m3u8").read_text(encoding="utf-8")
    return SimpleNamespace(id=ele.id, session=FakeSession({hls_url: playlist}), runs=runs)


@pytest.mark.parametrize("limit", list(LIMITS), ids=list(LIMITS))
def test_fansly_stream_size_skip_is_counted_and_downloaded_later(env, fansly, limit):
    size_min, size_max = LIMITS[limit](STREAM_SIZE)
    skip, _ = run_once(env, [fansly_item()[0]], fansly.session, size_min, size_max)
    assert skip == counts(forced_skipped=1)
    assert not downloaded(env, fansly.id)
    assert files(env) == []
    later, todo = run_once(env, [fansly_item()[0]], fansly.session)
    assert [ele.id for ele in todo] == [fansly.id]
    assert later == counts(video_count=1)
    assert downloaded(env, fansly.id) == 1
    assert files(env) == [b"\0" * STREAM_SIZE]
    assert len(fansly.runs) == 2


def test_fansly_stream_no_limits_unchanged(env, fansly):
    first, _ = run_once(env, [fansly_item()[0]], fansly.session)
    assert first == counts(video_count=1)
    assert downloaded(env, fansly.id) == 1
    second, again = run_once(env, [fansly_item()[0]], fansly.session)
    assert again == [] and second == counts()
    assert len(fansly.runs) == 1

# ------------------------------------------------------------- after-action script

@pytest.fixture
def action_script(env, monkeypatch, tmp_path):
    """The real after_download_action_script, with the script's run replaced:
    returns the media the script would get on stdin (#332)."""
    import ofscraper.managers.manager as manager
    import ofscraper.scripts.after_download_action_script as script_mod

    script = tmp_path / "script"
    script.write_text("")
    env.stub.after_action_script = str(script)
    monkeypatch.setattr(manager, "Manager", SimpleNamespace(current_model_manager=SimpleNamespace(
        get_model=lambda username: {"username": username, "id": MODEL_ID})))
    sent = []
    monkeypatch.setattr(script_mod, "run", lambda cmd, input=None, **k: sent.append(input))

    def media(items):
        script_mod.after_download_action_script(USERNAME, items)
        (payload,) = sent
        sent.clear()
        return json.loads(payload)["media"]

    return media


def saved(env, media_id):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        return conn.execute(
            "SELECT media_type, downloaded FROM medias WHERE media_id = ?", [media_id]
        ).fetchone()


def normal_item_run(env, name="abc123def", size_min=0, size_max=0):
    async def go():
        async with Server() as srv:
            async with sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                return await run_async(env, [photo(srv.base, name)], c, size_min, size_max)

    return asyncio.run(go())


@pytest.mark.parametrize("limit", list(LIMITS), ids=list(LIMITS))
def test_size_skip_reaches_action_script_as_skipped(env, action_script, limit):
    counted, todo = normal_item_run(env, size_min=LIMITS[limit](len(BODY))[0],
                                    size_max=LIMITS[limit](len(BODY))[1])
    # counted and saved as #319 leaves them
    assert counted == counts(forced_skipped=1)
    assert saved(env, 7) == ("Images", None)
    assert files(env) == []
    (media,) = action_script(todo)
    assert media["download_status"] == "skipped"
    assert media["type"] == "photo"


@pytest.mark.parametrize("limit", list(LIMITS), ids=list(LIMITS))
def test_fansly_stream_size_skip_reaches_action_script_as_skipped(
    env, fansly, action_script, limit
):
    size_min, size_max = LIMITS[limit](STREAM_SIZE)
    counted, todo = run_once(env, [fansly_item()[0]], fansly.session, size_min, size_max)
    assert counted == counts(forced_skipped=1)
    assert saved(env, fansly.id) == ("Videos", None)
    (media,) = action_script(todo)
    assert media["download_status"] == "skipped"
    assert media["type"] == "video"


def test_downloaded_item_reaches_action_script_unchanged(env, action_script):
    counted, todo = normal_item_run(env)
    assert counted == counts(photo_count=1)
    (media,) = action_script(todo)
    assert media["download_status"] == "succeeded"
    assert media["type"] == "photo"
    assert media["size"] == float(len(BODY))


def test_failed_item_reaches_action_script_unchanged(env, action_script):
    counted, todo = normal_item_run(env, name="gone123")
    assert counted == counts(skipped=1)
    assert not saved(env, 7)[1]
    (media,) = action_script(todo)
    assert media["download_status"] == "failed"
    assert media["type"] == "photo"
