import sys

import pytest

# the app parses sys.argv on import; don't let it see pytest's arguments
sys.argv = sys.argv[:1]

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as alt

BASE = "https://cdn3.onlyfans.com/dash/files/a/ab/abc"


@pytest.mark.parametrize(
    "mpd,segment,expected",
    [
        # with a query, the segment replaces the file name and keeps the query
        (f"{BASE}/123.mpd?Tag=2", "123_source.mp4", f"{BASE}/123_source.mp4?Tag=2"),
        (
            f"{BASE}/123.mpd?Tag=2&u=xxx",
            "123_audio.mp4",
            f"{BASE}/123_audio.mp4?Tag=2&u=xxx",
        ),
        # without a query, as before
        (f"{BASE}/123.mpd", "123_source.mp4", f"{BASE}/123_source.mp4"),
        # upper case and a leading slash on the segment name
        (f"{BASE}/ABC_1.MPD", "/abc_audio.mp4", f"{BASE}/abc_audio.mp4"),
    ],
)
def test_segment_url(mpd, segment, expected):
    assert alt._mpd_segment_url(mpd, segment) == expected
