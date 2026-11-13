import asyncio
import logging
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as alt


MPD = "https://cdn2.onlyfans.com/dash/files/a/ab/abc/0ib6w22s8j0j736isavja.mpd?Tag=2"


@pytest.mark.parametrize(
    "mpd,segment,expected",
    [
        # the shape OnlyFans serves: the segment keeps the MPD's query string
        (MPD, "0ib6w22s8j0j736isavja_source.mp4",
         "https://cdn2.onlyfans.com/dash/files/a/ab/abc/0ib6w22s8j0j736isavja_source.mp4?Tag=2"),
        ("https://cdn2.onlyfans.com/dash/files/a/abc.mpd", "abc_audio.mp4",
         "https://cdn2.onlyfans.com/dash/files/a/abc_audio.mp4"),
        ("https://cdn2.onlyfans.com/dash/files/a/ABC.MPD", "/abc_audio.mp4",
         "https://cdn2.onlyfans.com/dash/files/a/abc_audio.mp4"),
    ],
)
def test_segment_url(mpd, segment, expected):
    assert alt._mpd_segment_url(mpd, segment) == expected


def _ele(mediatype):
    return SimpleNamespace(
        mediatype=mediatype, id=1, postid=2, post_id=2, username="model",
        filename="f", final_filename="f", url=None, mpd=MPD, count=1,
    )


def test_zero_bytes_is_not_marked_downloaded(monkeypatch):
    manager = alt.AltDownloadManager()
    forced = []

    async def _force_download(*args, **kwargs):
        forced.append(args)

    monkeypatch.setattr(manager, "_force_download", _force_download, raising=False)
    monkeypatch.setattr(alt, "get_medialog", lambda ele: "", raising=False)
    with pytest.raises(Exception, match="0 bytes"):
        asyncio.run(
            manager._media_item_post_process_alt(
                {"total": 0}, {"total": 0}, _ele("videos"), "model", 1
            )
        )
    assert forced == []


def test_forced_skip_still_returns(monkeypatch):
    manager = alt.AltDownloadManager()
    result = asyncio.run(
        manager._media_item_post_process_alt(
            {"total": 0}, {"total": 0}, _ele("forced_skipped"), "model", 1
        )
    )
    assert result[1] == 0


def test_empty_cached_size_forces_fresh_request(monkeypatch):
    manager = alt.AltDownloadManager()
    cleared = []
    monkeypatch.setattr(alt.cache, "set", lambda key, value: cleared.append((key, value)))
    monkeypatch.setattr(alt, "get_medialog", lambda ele: "", raising=False)
    monkeypatch.setattr(alt.common_globals, "log", logging.getLogger("test"), raising=False)
    monkeypatch.setattr(alt.common_globals, "thread", None, raising=False)
    monkeypatch.setattr(alt.common_globals, "attempt", SimpleNamespace(get=lambda: 1), raising=False)
    monkeypatch.setattr(manager, "_get_resume_size", lambda placeholder: 0, raising=False)
    monkeypatch.setattr(manager, "_resume_cleaner", lambda size, total, path: 0, raising=False)

    class _Placeholder:
        tempfilepath = None

    item = {"name": "seg"}
    data = {"content-total": None}
    result = asyncio.run(
        manager._resume_data_handler_alt(data, item, _ele("videos"), _Placeholder())
    )
    assert result == (item, False)
    assert cleared and cleared[0][1] is None
