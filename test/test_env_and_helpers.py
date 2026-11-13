from types import SimpleNamespace

import pytest

from ofscraper.commands.scraper.actions.download.managers.alt_download import (
    _mpd_segment_url,
)
from ofscraper.prompts.prompt_validators import format_list, jsonloader, parse_list
from ofscraper.utils.dates import format_seconds
from ofscraper.utils.of_env.values.system import load_system_config
from ofscraper.utils.separate import separate_by_id


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, 10),
        ({"OFSC_LOG_SUBPROCESS_LEVEL": "20"}, 20),
        ({"OFSC_LOG_SUBPROCESS_LEVELL": "30"}, 30),  # old misspelling
        ({"OFSC_LOG_SUBPROCESS_LEVEL": "5", "OFSC_LOG_SUBPROCESS_LEVELL": "30"}, 5),
    ],
)
def test_log_subprocess_level_env(monkeypatch, env, expected):
    for key in ("OFSC_LOG_SUBPROCESS_LEVEL", "OFSC_LOG_SUBPROCESS_LEVELL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert load_system_config()["LOG_SUBPROCESS_LEVEL"] == expected


@pytest.mark.parametrize(
    "mpd, segment, expected",
    [
        (
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/name.mpd?Tag=2",
            "name_720p.mp4",
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/name_720p.mp4?Tag=2",
        ),
        (
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/name.mpd",
            "/audio.mp4",
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/audio.mp4",
        ),
        (
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/NAME.MPD",
            "v.mp4",
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/v.mp4",
        ),
        (
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/manifest",
            "v.mp4",
            "https://cdn3.onlyfans.com/dash/files/a/bc/hash/v.mp4",
        ),
    ],
)
def test_mpd_segment_url(mpd, segment, expected):
    assert _mpd_segment_url(mpd, segment) == expected


def test_separate_by_id():
    items = [SimpleNamespace(id=i) for i in (1, 2, 3)]
    assert [x.id for x in separate_by_id(items, [2])] == [1, 3]


@pytest.mark.parametrize(
    "seconds, expected",
    [(0, "00:00:00:00"), (59, "00:00:00:59"), (3661, "00:01:01:01"), (90061, "01:01:01:01")],
)
def test_format_seconds(seconds, expected):
    assert format_seconds(seconds) == expected


def test_list_round_trip():
    assert format_list(["a", "b"]) == "a,b"
    assert format_list("a,b") == "a,b"
    assert parse_list(" a, ,b ") == ["a", "b"]
    assert parse_list("") == []


def test_jsonloader():
    assert jsonloader('{"a": 1}') == {"a": 1}
    assert jsonloader("{bad") is None
    assert jsonloader(None) is None


def test_unencodable_output_is_replaced_not_raised():
    import io

    from rich.console import Console

    from ofscraper.utils.console import replace_unencodable_output

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    replace_unencodable_output([stream])
    Console(file=stream, force_terminal=False).print("Cherry \U0001F352 model")
    stream.flush()
    assert stream.buffer.getvalue().decode("cp1252").strip() == "Cherry ? model"


def test_utf8_output_is_left_alone():
    import io

    from ofscraper.utils.console import replace_unencodable_output

    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    replace_unencodable_output([stream])
    assert stream.errors == "strict"
