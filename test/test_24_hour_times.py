"""Times in the check table and the scrape summary use a 24-hour clock (#335).

They were formatted with arrow's ``hh`` (12-hour) and no AM/PM, so a post
from 20:00 showed as 08:00:00. File and folder names come from the
``{date}`` placeholder and the user's ``date`` setting, not from these
properties, so they must stay as they were.
"""

import asyncio
import pathlib
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.check as check
import ofscraper.commands.utils.scrape_context as scrape_context
from ofscraper.classes.of.posts import Post

EVENING = "2024-05-01T20:00:00+00:00"
MODEL_ID = 1000
USERNAME = "a_creator"


def evening_post():
    raw = {
        "id": 2000,
        "postedAt": EVENING,
        "text": "",
        "price": 0,
        "media": [
            {
                "id": 3000,
                "type": "photo",
                "canView": True,
                "createdAt": EVENING,
                "files": {"full": {"url": "https://example.invalid/a.jpg"}},
            }
        ],
    }
    return Post(raw, MODEL_ID, USERNAME, "timeline")


def test_check_table_shows_an_evening_post_on_a_24_hour_clock(monkeypatch):
    media = evening_post().all_media
    collection = SimpleNamespace(all_media=media, posts_with_media_id=lambda _id: [])
    monkeypatch.setattr(check, "get_media_post_files_downloaded", lambda **kw: {})
    monkeypatch.setattr(check, "check_user_dict", {str(MODEL_ID): {"collection": collection}})
    monkeypatch.setattr(check, "ROWS", [])

    asyncio.run(check.row_gather(USERNAME, MODEL_ID))

    assert [row["post_date"] for row in check.ROWS] == ["2024-05-01 20:00:00"]


def test_media_and_post_dates_use_a_24_hour_clock():
    post = evening_post()
    media = post.all_media[0]
    assert post.formatted_date == "2024-05-01 20:00:00"
    assert media.formatted_postdate == "2024-05-01 20:00:00"
    assert media.formatted_date == "2024-05-01 20:00:00"


def test_scrape_summary_shows_evening_times_on_a_24_hour_clock(monkeypatch):
    times = iter(
        [
            scrape_context.datetime(2024, 5, 1, 19, 30, 15),
            scrape_context.datetime(2024, 5, 1, 21, 45, 30),
        ]
    )
    monkeypatch.setattr(
        scrape_context, "datetime", SimpleNamespace(now=lambda: next(times))
    )
    lines = []
    monkeypatch.setattr(scrape_context.log, "info", lambda *a, **k: None)
    monkeypatch.setattr(scrape_context.log, "warning", lambda msg, *a, **k: lines.append(msg))

    with scrape_context.scrape_context_manager():
        pass

    (summary,) = lines
    assert "Started At:  [bold]2024-05-01 19:30:15[/bold]" in summary
    assert "Finished At:  [bold]2024-05-01 21:45:30[/bold]" in summary
    assert "Run Time:  [bold]2:15:15[/bold]" in summary


@pytest.fixture
def placeholder_env(monkeypatch, tmp_path):
    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(placeholder.common_paths, "get_save_location",
                        lambda *a, **k: str(tmp_path / "data"))
    monkeypatch.setattr(placeholder.config_file, "open_config", lambda: {})
    monkeypatch.setattr(placeholder.settings, "get_args", lambda: SimpleNamespace())
    monkeypatch.setattr(
        placeholder.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(get_model=lambda _u: None)),
    )
    monkeypatch.setattr(placeholder, "naming_script", lambda *a, **k: _none())
    return tmp_path


async def _none():
    return None


@pytest.mark.parametrize(
    "date_format, expected",
    [
        # a user's own 12-hour format keeps giving the same names
        ("YYYY-MM-DD_hh-mm-ss", "2024-05-01_08-00-00"),
        ("YYYY-MM-DD_HH-mm-ss", "2024-05-01_20-00-00"),
        ("MM-DD-YYYY", "05-01-2024"),
    ],
)
def test_date_placeholder_in_folder_and_file_names_is_unchanged(
    monkeypatch, placeholder_env, date_format, expected
):
    media = evening_post().all_media[0]
    monkeypatch.setattr(placeholder.data, "get_date", lambda *a, **k: date_format)
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: "{date}")
    monkeypatch.setattr(placeholder.data, "get_fileformat", lambda *a, **k: "{date}.{ext}")

    names = placeholder.Placeholders(media, "jpg")
    folder = asyncio.run(names.getmediadir(create=False))
    file_name = asyncio.run(names.createfilename())

    assert pathlib.Path(folder).name == expected
    assert file_name == f"{expected}.jpg"
    assert arrow.get(media.postdate).format(date_format) == expected
