"""`ofscraper db` on media rows with no date (#366).

A row with an empty posted_at or created_at shows an empty date, and the date
filters and sorts don't crash on it. Dated rows come out as before. Also: the
export with a date format arrow can't read back, and the printed table's
column order (#368).
"""

import asyncio
import contextlib
import csv
import inspect
import io
import re
import sqlite3
from types import SimpleNamespace

import arrow
import pytest
from rich.console import Console

import ofscraper.commands.db as db_command
import ofscraper.db.operations_.media as media_ops

ALL_AREAS = ["Timeline", "Pinned", "Archived", "Messages", "Streams", "Highlights", "Stories"]
READERS = [
    "get_all_medias",
    "get_timeline_media",
    "get_archived_media",
    "get_messages_media",
    "get_streams_media",
    "get_pinned_media",
    "get_highlights_media",
    "get_stories_media",
]


def media_row(media_id, posted_at, created_at, api_type="timeline"):
    return {
        "media_id": media_id,
        "post_id": 100 + media_id,
        "link": "https://example.invalid/a.jpg",
        "filename": f"{media_id}.jpg",
        "size": 2048,
        "api_type": api_type,
        "media_type": "Images",
        "downloaded": 1,
        "created_at": created_at,
        "posted_at": posted_at,
        "model_id": 5,
    }


ROWS = [
    media_row(1, "2024-01-02T10:00:00", "2024-01-01T10:00:00"),
    media_row(2, None, "2024-02-01T10:00:00"),
    media_row(3, "2024-03-02T10:00:00", ""),
]


def make_db(path, rows):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(media_ops.mediaCreate)
        for row in rows:
            conn.execute(
                f"INSERT INTO medias ({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                list(row.values()),
            )
        conn.commit()


@pytest.fixture
def run_db(monkeypatch, tmp_path):
    """Run the `ofscraper db` command on one database; returns (csv rows, table text)."""

    def run(rows, areas=ALL_AREAS, **options):
        path = tmp_path / "user_data.db"
        make_db(path, rows)
        export = tmp_path / "out"
        args = SimpleNamespace(
            download_area=areas,
            downloaded=None,
            protected=False,
            normal=False,
            unlocked=None,
            preview=None,
            post_id=None,
            media_id=None,
        )
        settings = SimpleNamespace(
            size_max=None,
            size_min=None,
            length_max=None,
            length_min=None,
            posted_before=None,
            posted_after=None,
            created_after=None,
            created_before=None,
            mediatypes=["Audios", "Videos", "Images"],
            max_post_count=None,
            db_asc=True,
            db_sort="mediaid",
            export=export,
        )
        for key, value in options.items():
            setattr(settings, key, value)
        monkeypatch.setattr(db_command.settings, "get_args", lambda: args)
        monkeypatch.setattr(db_command.settings, "get_settings", lambda: settings)

        # the real readers, on this database
        for name in READERS:

            async def reader(real=getattr(media_ops, name), **kwargs):
                result = real(**kwargs, db_path=path)
                return await result if inspect.isawaitable(result) else result

            monkeypatch.setattr(db_command, name, reader)
        model = SimpleNamespace(name="a creator", id=5)
        model_manager = SimpleNamespace(all_subs=[model], sync_models=lambda **kwargs: None)
        monkeypatch.setattr(
            db_command.manager, "Manager", SimpleNamespace(current_model_manager=model_manager)
        )
        monkeypatch.setattr(db_command.actions, "select_areas", lambda: None)
        monkeypatch.setattr(db_command.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(db_command, "add_other_handler", lambda log: None)
        out = io.StringIO()
        console = Console(file=out, width=400)
        monkeypatch.setattr(db_command.console, "get_console", lambda: console)

        # the command's run() keeps the current loop open; close it after
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            db_command.db()
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        with open(export.with_suffix(".csv"), newline="") as f:
            written = list(csv.DictReader(f))
        return written, out.getvalue()

    return run


def dates(written):
    return [(int(r["media_id"]), r["posted_at"], r["created_at"]) for r in written]


def test_empty_dates_show_empty(run_db):
    # Given a row with no posted_at and a row with no created_at
    # When ofscraper db runs
    written, table = run_db(ROWS)

    # Then nothing crashes, and those rows show an empty date
    assert dates(written) == [
        (1, "2024-01-02 10:00:00", "2024-01-01 10:00:00"),
        (2, "", "2024-02-01 10:00:00"),
        (3, "2024-03-02 10:00:00", ""),
    ]
    # and the printed table shows only the dates each row has
    for name, count in (("1.jpg", 2), ("2.jpg", 1), ("3.jpg", 1)):
        line = next(line for line in table.splitlines() if name in line)
        assert line.count("2024-") == count
    assert "1970" not in table


def test_dated_rows_unchanged(run_db):
    # Given rows that all have dates, the output is what it was before
    fmt = "YYYY-MM-DD HH:mm:ss"
    written, _ = run_db([ROWS[0]])
    assert dates(written) == [
        (
            1,
            arrow.get(ROWS[0]["posted_at"]).format(fmt),
            arrow.get(ROWS[0]["created_at"]).format(fmt),
        )
    ]
    assert written[0]["size_human"] == "2.05 KB"


@pytest.mark.parametrize(
    "option,value,expected",
    [
        # a row with no date counts as the oldest date, as before
        ("posted_before", arrow.get("2024-02-01"), [1, 2]),
        ("posted_after", arrow.get("2024-01-01"), [1, 3]),
        ("created_before", arrow.get("2024-01-15"), [1, 3]),
        ("created_after", arrow.get("2024-01-15"), [2]),
    ],
)
def test_date_filters_with_empty_dates(run_db, option, value, expected):
    written, _ = run_db(ROWS, **{option: value})
    assert [int(r["media_id"]) for r in written] == expected


@pytest.mark.parametrize(
    "sort,asc,expected",
    [
        ("posted", True, [2, 1, 3]),
        ("posted", False, [3, 1, 2]),
        ("created", True, [3, 1, 2]),
        ("created", False, [2, 1, 3]),
    ],
)
def test_date_sorts_with_empty_dates(run_db, sort, asc, expected):
    written, _ = run_db(ROWS, db_sort=sort, db_asc=asc)
    assert [int(r["media_id"]) for r in written] == expected


def area_rows(api_type):
    return [
        media_row(1, "2024-01-02T10:00:00", "2024-01-01T10:00:00", api_type),
        media_row(2, None, "2024-02-01T10:00:00", api_type),
        media_row(3, "2024-03-02T10:00:00", "", api_type),
        media_row(4, None, None, api_type),
        media_row(5, "", "", api_type),
    ]


@pytest.mark.parametrize("area,api_type", [("Timeline", "timeline"), ("Messages", "messages")])
def test_one_area_empty_dates_show_empty(run_db, area, api_type):
    # Given rows with missing dates, when ofscraper db runs on one area
    written, table = run_db(area_rows(api_type), areas=[area])

    # Then a row with neither date shows empty dates, not 1970; a row with no
    # posted date still shows its created date as posted, as before
    assert dates(written) == [
        (1, "2024-01-02 10:00:00", "2024-01-01 10:00:00"),
        (2, "2024-02-01 10:00:00", "2024-02-01 10:00:00"),
        (3, "2024-03-02 10:00:00", ""),
        (4, "", ""),
        (5, "", ""),
    ]
    assert "1970" not in table


@pytest.mark.parametrize(
    "options,expected",
    [
        ({"db_sort": "posted", "db_asc": True}, [4, 5, 1, 2, 3]),
        ({"db_sort": "posted", "db_asc": False}, [3, 2, 1, 4, 5]),
        ({"posted_before": arrow.get("2024-01-15")}, [1, 4, 5]),
        ({"posted_after": arrow.get("2024-01-15")}, [2, 3]),
    ],
)
def test_one_area_date_sorts_and_filters(run_db, options, expected):
    written, _ = run_db(area_rows("timeline"), areas=["Timeline"], **options)
    assert [int(r["media_id"]) for r in written] == expected


def test_export_with_custom_date_format(run_db, monkeypatch):
    # Given a date format arrow can't read back
    real = db_command.of_env.getattr

    def getattr_(key, *args, **kwargs):
        if key == "API_DATE_FORMAT":
            return "DD/MM/YYYY HH:mm"
        return real(key, *args, **kwargs)

    monkeypatch.setattr(db_command.of_env, "getattr", getattr_)

    # When ofscraper db --export runs, the dates use that format
    written, _ = run_db(ROWS)
    assert dates(written) == [
        (1, "02/01/2024 10:00", "01/01/2024 10:00"),
        (2, "", "01/02/2024 10:00"),
        (3, "02/03/2024 10:00", ""),
    ]


# the export's columns on main before #366, for a dated row
MAIN_HEADER_ALL_AREAS = [
    "media_id", "post_id", "directory", "filename", "api_type", "media_type",
    "preview", "downloaded", "created_at", "unlocked", "model_id", "posted_at",
    "hash", "duration", "skip_permanent", "size_human", "size",
]
# plus skip_permanent, which all-areas output already had (#371)
MAIN_HEADER_ONE_AREA = [
    "media_id", "post_id", "directory", "filename", "api_type", "media_type",
    "preview", "downloaded", "created_at", "posted_at", "hash", "model_id",
    "unlocked", "duration", "skip_permanent", "size_human", "size",
]


@pytest.mark.parametrize(
    "areas,api_type,expected",
    [
        (ALL_AREAS, "timeline", MAIN_HEADER_ALL_AREAS),
        (["Timeline"], "timeline", MAIN_HEADER_ONE_AREA),
        (["Messages"], "messages", MAIN_HEADER_ONE_AREA),
    ],
)
def test_export_columns_unchanged(run_db, areas, api_type, expected):
    # anything reading the CSV by position keeps working
    written, _ = run_db([dict(ROWS[0], api_type=api_type)], areas=areas)
    assert list(written[0]) == expected


def test_table_columns_follow_the_export(run_db):
    # The printed table's columns are in the same order as the CSV's (#368)
    written, table = run_db(ROWS)
    header = next(line for line in table.splitlines() if "media_id" in line)
    columns = [cell.strip() for cell in re.split("[┃│]", header) if cell.strip()]
    assert columns == list(written[0])
