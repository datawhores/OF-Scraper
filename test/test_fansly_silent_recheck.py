"""Fansly videos saved without sound because the CDN refused their audio are
checked again, ``SILENT_RECHECKS`` times, and downloaded again once the audio
is accepted.

No request is sent anywhere: ``account/media``, the audio check and the
download are faked, and the profile cache is a dict.
"""

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.commands.scraper.actions.download.utils import silent
from ofscraper.sites.fansly import normalize

MODEL = 100000000000000002


def raw_post(n, kind="post"):
    out = {"id": 3000 + n, "text": "", "createdAt": "2026-01-02T03:04:05+00:00",
           "postedAt": "2026-01-02T03:04:05+00:00", "price": 0, "isOpened": True,
           "responseType": kind, "hashtags": []}
    if kind == "message":
        out.update(fromUser={"id": MODEL}, groupId="77")
    return out


def make_ele(n, kind="post", area=None):
    post = SimpleNamespace(_post={**raw_post(n, kind), "media": [{"id": 2000 + n}]},
                           _responsetype=area, _label=None, _purchased=False)
    return SimpleNamespace(
        id=2000 + n,
        post_id=3000 + n,
        media={"fansly": {"accountMediaId": str(1000 + n), "media": {"id": str(2000 + n)},
                          "isPreview": False}},
        replace_silent=None,
        _post=post,
    )


def answer(n):
    return {"id": str(1000 + n), "access": True,
            "media": {"id": str(2000 + n), "mimetype": "video/mp4", "variants": [{}],
                      "locations": [{"locationId": "1", "location": "https://cdn.test/v.mp4"}]}}


@pytest.fixture
def run(monkeypatch):
    store = {}
    state = SimpleNamespace(
        store=store, asked=[], checks=[], downloads=[], verdict=silent.REFUSED,
        saved=True, api_error=None, answers=None, mediatypes=["Images", "Videos"],
        posts=None, posts_error=None, posts_asked=[], on_download=None,
        saved_path=None,
    )

    def get(key, default=None):
        return store.get(key, default)

    def set_(key, value, **kw):
        store[key] = value

    @asynccontextmanager
    async def session(**kwargs):
        yield "api"

    async def account_media(c, ids):
        state.asked.append(list(ids))
        if state.api_error:
            raise state.api_error
        return [answer(int(i) - 1000) for i in ids] if state.answers is None else state.answers

    async def check_audio(c, raw):
        state.checks.append(raw["id"])
        verdict = state.verdict
        if isinstance(verdict, Exception):
            raise verdict
        return verdict

    async def download(c, ele):
        state.downloads.append((ele.id, ele.replace_silent))
        if state.on_download:
            await state.on_download(ele)
        return state.saved

    async def posts_by_id(c, ids):
        state.posts_asked.append(list(ids))
        if state.posts_error:
            raise state.posts_error
        return state.posts or []

    real = settings.get_settings()
    monkeypatch.setattr(
        settings, "get_settings",
        lambda: SimpleNamespace(**{**dict(real), "mediatypes": state.mediatypes,
                                   "cached_disabled": False}),
    )
    monkeypatch.setattr(silent.cache, "get", get)
    monkeypatch.setattr(silent.cache, "set", set_)
    monkeypatch.setattr(silent.fansly_api, "account_media", account_media)
    monkeypatch.setattr(silent.fansly_api, "posts_by_id", posts_by_id)
    monkeypatch.setattr(
        silent.manager, "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=session)),
    )

    def once(media=()):
        by_id = {str(m.id): m for m in media}
        asyncio.run(
            silent.recheck(
                "dl", "a-creator", MODEL, by_id, check_audio, download, state.saved_path
            )
        )

    state.once = once
    return state


def test_a_refused_check_uses_one_check_and_downloads_nothing(run):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    run.once([ele])
    assert run.asked == [["1000"]] and run.checks == ["2000"]
    assert run.downloads == []
    assert silent.flags(MODEL)["2000"]["checks"] == 1


def test_accepted_audio_downloads_again_in_replace_mode_and_drops_the_flag(run):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    run.verdict = silent.ACCEPTED
    run.once([ele])
    assert run.downloads == [(2000, "out/video.mp4")]
    assert ele.replace_silent is None
    # the fresh links are what the download uses
    assert ele.media["fansly"]["media"] == answer(0)["media"]
    assert silent.flags(MODEL) == {}


def test_a_failed_download_again_keeps_the_flag_and_uses_no_check(run):
    # download() answers ("skipped", 0) for a network or disk failure
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    run.verdict, run.saved = silent.ACCEPTED, False
    for _ in range(silent.limit() + 1):
        run.once([ele])
    assert len(run.downloads) == silent.limit() + 1
    assert silent.flags(MODEL)["2000"]["checks"] == 0


def test_a_new_copy_still_without_sound_uses_a_check(run):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    run.verdict, run.saved = silent.ACCEPTED, silent.REFUSED
    run.once([ele])
    assert silent.flags(MODEL)["2000"]["checks"] == 1


def test_a_copy_with_sound_that_is_not_kept_uses_a_check(run):
    # over the size limit, skipped by skip_download_script, or the silent
    # file can't be replaced: the next run would end the same way
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    run.verdict, run.saved = silent.ACCEPTED, silent.NOT_KEPT
    for _ in range(silent.limit() + 2):
        run.once([ele])
    assert len(run.downloads) == silent.limit()
    assert silent.flags(MODEL) == {}


def test_a_silent_file_that_was_moved_is_found_where_the_database_has_it(run, tmp_path):
    ele = make_ele(0)
    flagged, moved = tmp_path / "old" / "video.mp4", tmp_path / "new" / "video.mp4"
    moved.parent.mkdir()
    moved.write_bytes(b"silent copy")
    silent.flag(MODEL, ele, flagged)
    asked = []

    async def saved_path(item):
        asked.append(item.id)
        return moved

    run.verdict, run.saved, run.saved_path = silent.ACCEPTED, False, saved_path
    run.once([ele])
    assert run.downloads == [(2000, str(moved))]
    # a file still at the flag's path is the one replaced
    flagged.parent.mkdir()
    flagged.write_bytes(b"silent copy")
    asked.clear()
    run.once([ele])
    assert run.downloads[-1] == (2000, str(flagged)) and asked == []
    # nowhere: the flag's path, where the copy with sound is then saved
    flagged.unlink()
    moved.unlink()
    run.once([ele])
    assert run.downloads[-1] == (2000, str(flagged))


def test_after_the_last_refused_check_the_flag_goes_and_no_more_checks_run(run, caplog):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    with caplog.at_level("INFO", logger="shared"):
        for _ in range(silent.limit()):
            run.once([ele])
    assert silent.flags(MODEL) == {}
    assert "keeping the video without sound" in caplog.text and "2000" in caplog.text
    run.once([ele])
    assert len(run.asked) == silent.limit() == 3


@pytest.mark.parametrize("failure", ["check", "api"])
def test_a_check_that_fails_for_another_reason_uses_nothing(run, failure):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    if failure == "check":
        run.verdict = silent.FAILED
    else:
        run.api_error = RuntimeError("429")
    run.once([ele])
    run.verdict = ConnectionError("reset")
    run.api_error = None
    run.once([ele])
    assert silent.flags(MODEL)["2000"]["checks"] == 0


def test_gone_media_uses_a_check_so_the_flag_does_not_live_forever(run):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/video.mp4")
    run.answers = []
    run.once([ele])
    assert run.checks == []
    assert silent.flags(MODEL)["2000"]["checks"] == 1


def test_a_run_without_videos_skips_the_checks(run):
    silent.flag(MODEL, make_ele(0), "out/video.mp4")
    run.mediatypes = ["Images"]
    run.once()
    assert run.asked == [] and silent.flags(MODEL)["2000"]["checks"] == 0


def test_one_call_fetches_links_for_every_flagged_video(run):
    eles = [make_ele(n) for n in range(3)]
    for ele in eles:
        silent.flag(MODEL, ele, f"out/{ele.id}.mp4")
    run.once(eles)
    assert run.asked == [["1000", "1001", "1002"]]
    assert sorted(run.checks) == ["2000", "2001", "2002"]


def test_a_timeline_video_this_run_did_not_scan_is_built_from_its_post(run):
    # an early stop: the old post isn't scanned, so it is fetched by id
    silent.flag(MODEL, make_ele(0), "out/video.mp4")
    run.verdict = silent.ACCEPTED
    run.posts = [{**raw_post(0), "media": normalize.media_for(answer(0))}]
    run.once([])
    assert run.posts_asked == [["3000"]]
    assert run.downloads == [(2000, "out/video.mp4")]
    assert silent.flags(MODEL) == {}


def test_a_message_video_this_run_did_not_scan_is_built_from_its_flag(run, monkeypatch):
    built = []
    real = silent.posts_.Post

    def post(*args, **kwargs):
        found = real(*args, **kwargs)
        built.append(found)
        return found

    monkeypatch.setattr(silent.posts_, "Post", post)
    silent.flag(MODEL, make_ele(0, kind="message"), "out/video.mp4")
    run.verdict = silent.ACCEPTED
    run.once([])
    # no call fetches one message: the copy kept in the flag and the fresh links
    assert run.posts_asked == []
    assert run.downloads == [(2000, "out/video.mp4")]
    assert built[0].responsetype == "Messages" and built[0].id == 3000
    assert silent.flags(MODEL) == {}


@pytest.mark.parametrize("case, checks", [("gone", 1), ("fetch failed", 0)])
def test_a_post_that_cannot_be_fetched_downloads_nothing(run, case, checks):
    silent.flag(MODEL, make_ele(0), "out/video.mp4")
    run.verdict = silent.ACCEPTED
    if case == "gone":
        run.posts = []
    else:
        run.posts_error = ConnectionError("reset")
    run.once([])
    assert run.downloads == []
    assert silent.flags(MODEL)["2000"]["checks"] == checks


def test_flags_saved_at_once_are_all_kept(run, monkeypatch):
    real_get = silent.cache.get

    def slow_get(key, default=None):
        found = real_get(key, default)
        time.sleep(0.05)
        return found

    monkeypatch.setattr(silent.cache, "get", slow_get)
    eles = [make_ele(n) for n in range(4)]
    threads = [threading.Thread(target=silent.flag, args=(MODEL, e, f"out/{e.id}.mp4"))
               for e in eles]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(silent.flags(MODEL)) == ["2000", "2001", "2002", "2003"]


def test_a_flagged_preview_is_checked_with_its_own_links(run):
    ele = make_ele(0)
    ele.media["fansly"]["isPreview"] = True
    silent.flag(MODEL, ele, "out/p.mp4")
    run.answers = [{"id": "1000", "media": {"id": "9999", "variants": [{}]},
                    "preview": {"id": "2000", "variants": [{}]}}]
    run.once([ele])
    assert run.checks == ["2000"]
    assert silent.flags(MODEL)["2000"]["checks"] == 1


def test_ctrl_c_stops_the_checks(run):
    eles = [make_ele(n) for n in range(3)]
    for ele in eles:
        silent.flag(MODEL, ele, f"out/{ele.id}.mp4")
    run.verdict = silent.ACCEPTED

    async def stop_now(ele):
        stop.request()
        await asyncio.sleep(30)  # cancelled: it runs inside stop.transfer

    run.on_download = stop_now
    try:
        run.once(eles)
    finally:
        stop.clear()
    assert len(run.downloads) == 1
    # the stopped download uses nothing, the others aren't checked
    assert len(run.checks) == 1
    assert all(r["checks"] == 0 for r in silent.flags(MODEL).values())
    assert len(silent.flags(MODEL)) == 3


def test_flagging_again_keeps_the_count_and_clear_removes_it(run):
    ele = make_ele(0)
    silent.flag(MODEL, ele, "out/old.mp4")
    run.once([ele])
    silent.flag(MODEL, ele, "out/new.mp4")
    record = silent.flags(MODEL)["2000"]
    assert record["checks"] == 1 and record["path"] == "out/new.mp4"
    silent.clear(MODEL, ele.id)
    assert silent.flags(MODEL) == {}


@pytest.mark.parametrize("site, stopped, expected", [
    ("fansly", False, True), ("onlyfans", False, False), ("fansly", True, False),
])
def test_the_checks_run_after_a_fansly_creator_s_downloads(monkeypatch, site, stopped, expected):
    import ofscraper.commands.scraper.actions.download.download as download_mod

    calls = []

    async def download_process(*a, **k):
        calls.append("download")
        return (0, 0, 0, 0, 0)

    async def recheck_silent(username, model_id, all_media):
        calls.append(("recheck", username, model_id, all_media))

    monkeypatch.setattr(download_mod, "download_process", download_process)
    monkeypatch.setattr(download_mod, "recheck_silent", recheck_silent)
    monkeypatch.setattr(download_mod.sites, "is_fansly", lambda: site == "fansly")
    if stopped:
        download_mod.stop.requested.set()
    try:
        asyncio.run(download_mod.downloader(
            username="a-creator", model_id=MODEL, posts=[], media=["new"],
            all_media=["new", "saved earlier"]))
    finally:
        download_mod.stop.requested.clear()
    assert calls[0] == "download"
    assert calls[1:] == ([("recheck", "a-creator", MODEL, ["new", "saved earlier"])]
                         if expected else [])


def test_no_checks_when_the_limit_is_zero(run, monkeypatch):
    monkeypatch.setenv("OFSC_SILENT_RECHECKS", "0")
    monkeypatch.setattr(silent, "limit", lambda: 0)
    silent.flag(MODEL, make_ele(0), "out/video.mp4")
    assert silent.flags(MODEL) == {}


def test_a_copy_not_kept_for_its_size_leaves_the_video_in_the_runs_counts(monkeypatch):
    import ofscraper.commands.scraper.actions.download.download as download_mod
    from ofscraper.classes.of.media import Media
    from ofscraper.classes.of.posts import Post
    from ofscraper.managers.stats import DownloadStats, StatsManager

    post = Post({"id": 3001, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
                MODEL, "a-creator", responsetype="timeline")
    ele = Media({"id": 2001, "type": "video", "canView": True, "size": 1000}, 0, post)
    # saved without sound earlier in this run
    ele.mark_download_succeeded()

    async def too_big(c, ele, model_id, username):
        # what the stream downloader does with a copy over size_max
        ele.mediatype = "Forced_skipped"
        ele.not_kept = "the copy with sound was skipped by the size limits"
        return "forced_skipped", 0

    monkeypatch.setattr(download_mod, "download", too_big)
    again = asyncio.run(download_mod._download_again(None, ele, MODEL, "a-creator"))
    assert again == silent.NOT_KEPT
    stats = DownloadStats("a-creator")
    StatsManager._update_download_stats_helper(None, stats, [ele])
    assert (stats.video_count, stats.skipped_count, stats.failed_count) == (1, 0, 0)
