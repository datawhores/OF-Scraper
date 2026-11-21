import asyncio
import contextlib
import csv
import datetime
import importlib.util
import os
import pathlib
import sqlite3
import subprocess
import sys
import time
from unittest import mock

import arrow
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations_.profile as profile

ROOT = pathlib.Path(__file__).resolve().parents[1]
URL_KEY = "OFSC_DATABASE_URL"
URL = "postgresql://user:password@localhost/db"

_spec = importlib.util.spec_from_file_location(
    "creator_names",
    ROOT / "scripts" / "creator_names.py",
)
creator_names = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(creator_names)

# The table as OF-Scraper makes it today, and as it made it before it kept the dates a
# name was seen at (#643)
PROFILES = profile.profilesCreate
PROFILES_BEFORE_THE_DATES = """
CREATE TABLE profiles (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username VARCHAR NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (user_id, username)
)
"""
MARCH = "2024-03-01T09:30:00+00:00"
APRIL = "2024-04-01T09:30:00+00:00"
MAY = "2024-05-01T09:30:00+00:00"
NO_DATES = (None, None)


def _account(data_dir, model_id, names, media=0, dates=True):
    """A database with the names, each either a name or (name, first seen, last seen).
    dates=False makes one from before the dates were kept."""
    db = data_dir / str(model_id) / "user_data.db"
    db.parent.mkdir(parents=True)
    names = [(n, None, None) if isinstance(n, str) else n for n in names]
    with contextlib.closing(sqlite3.connect(db)) as con:
        con.execute("CREATE TABLE medias (id INTEGER PRIMARY KEY, media_id INTEGER)")
        if dates:
            con.execute(PROFILES)
            con.executemany(
                "INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at)"
                " VALUES (?, ?, ?, ?)",
                [(model_id, *n) for n in names],
            )
        else:
            con.execute(PROFILES_BEFORE_THE_DATES)
            con.executemany(
                "INSERT INTO profiles (user_id, username) VALUES (?, ?)",
                [(model_id, n[0]) for n in names],
            )
        con.executemany("INSERT INTO medias (media_id) VALUES (?)", [(i,) for i in range(media)])
        con.commit()
    return db


def _names(db):
    with contextlib.closing(sqlite3.connect(db)) as con:
        return [r[0] for r in con.execute("SELECT username FROM profiles ORDER BY id")]


def _dates(db):
    with contextlib.closing(sqlite3.connect(db)) as con:
        return {
            r[0]: r[1:]
            for r in con.execute("SELECT username, first_seen_at, last_seen_at FROM profiles")
        }


def _app_folder_name(db, model_id):
    """The name OF-Scraper itself picks for a deleted account, by its own code."""
    with mock.patch.object(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    ):
        return asyncio.run(profile.get_profile_info(model_id=model_id, username="x"))


def _app_works_on(db, model_id, name):
    """OF-Scraper starts work on the account under a name, by its own code."""
    with mock.patch.object(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    ):
        asyncio.run(profile.write_profile_table(model_id=model_id, username=name))


def _folder_name(db, model_id):
    with contextlib.closing(sqlite3.connect(db)) as con:
        return creator_names.folder_name(con, model_id)


def test_the_script_runs_the_queries_the_scraper_runs():
    def same(query):
        return " ".join(query.split())

    assert same(creator_names.FOLDER_NAME) == same(profile.deletedAccountName)
    assert same(creator_names.FOLDER_NAME_UNDATED) == same(profile.deletedAccountNameUndated)
    assert list(creator_names.placeholder_names(7)) == profile.placeholder_names(7)


def test_lists_only_accounts_with_several_names(tmp_path):
    _account(tmp_path, 1, ["current_name", "old_name"], media=3)
    _account(tmp_path, 2, ["only_name"])
    rows = creator_names.select(tmp_path)
    assert rows == [("1", ["current_name", "old_name"], 3, "current_name", [NO_DATES] * 2)]
    assert len(creator_names.select(tmp_path, show_all=True)) == 2


def test_listing_shows_the_folder_name_the_app_uses(tmp_path):
    # recorded first isn't what the app picks: without dates it goes by the alphabet
    db = _account(tmp_path, 1, ["zeta_name", "alpha_name"])
    (row,) = creator_names.select(tmp_path)
    assert row[1][0] == "zeta_name"
    assert row[3] == "alpha_name" == _app_folder_name(db, 1)


def test_the_folder_name_is_the_name_seen_last(tmp_path):
    # not the first by the alphabet, and not the one recorded last
    db = _account(
        tmp_path,
        1,
        [("middle_name", MARCH, MAY), ("alpha_name", MARCH, APRIL), "zeta_name"],
    )
    (row,) = creator_names.select(tmp_path)
    assert row[3] == "middle_name" == _app_folder_name(db, 1)
    assert row[4] == [(MARCH, MAY), (MARCH, APRIL), NO_DATES]


@pytest.mark.parametrize("dates", [True, False])
def test_the_folder_name_is_not_the_placeholder_while_a_name_is_known(tmp_path, dates):
    stand_ins = creator_names.placeholder_names(1)
    db = _account(tmp_path, 1, [*stand_ins, "zeta_name"], dates=dates)
    (row,) = creator_names.select(tmp_path)
    assert row[3] == "zeta_name" == _app_folder_name(db, 1)


@pytest.mark.parametrize("names", [["zeta_name", "Beta_name", "alpha_name"], ["b", "B", "a1"]])
def test_a_database_from_before_the_dates_is_listed_without_them(tmp_path, names):
    db = _account(tmp_path, 1, names, dates=False)
    (row,) = creator_names.select(tmp_path)
    assert row[1] == names
    assert row[4] == [NO_DATES] * len(names)
    # capital letters first, as in a database with the columns
    assert row[3] == sorted(names)[0] == _app_folder_name(db, 1)


def test_find_matches_any_recorded_name_case_insensitively(tmp_path):
    _account(tmp_path, 1, ["current_name", "Old_Name"])
    _account(tmp_path, 2, ["someone_else"])
    assert [r[0] for r in creator_names.select(tmp_path, find="old_name")] == ["1"]
    assert creator_names.select(tmp_path, find="never_used") == []


def test_add_appends_a_name_that_keeps_the_folder_name(tmp_path):
    db = _account(tmp_path, 7, ["alpha_name"])
    assert creator_names.add_name(tmp_path, 7, "zeta_name") is True
    assert creator_names.add_name(tmp_path, "7", "zeta_name") is False
    assert _names(db) == ["alpha_name", "zeta_name"]
    assert _dates(db) == {"alpha_name": NO_DATES, "zeta_name": NO_DATES}
    assert _app_folder_name(db, 7) == "alpha_name"


def test_add_refuses_a_name_that_would_change_the_folder_name(tmp_path):
    # without dates OF-Scraper names a deleted account's folder after the first name by
    # the alphabet; alpha_name would take over from zeta_name
    db = _account(tmp_path, 7, ["zeta_name"])
    with pytest.raises(creator_names.FolderNameWouldChange):
        creator_names.add_name(tmp_path, 7, "alpha_name")
    assert _names(db) == ["zeta_name"]
    assert _app_folder_name(db, 7) == "zeta_name"


def test_add_with_force_changes_the_folder_name(tmp_path):
    db = _account(tmp_path, 7, ["zeta_name"])
    assert creator_names.add_name(tmp_path, 7, "alpha_name", force=True) is True
    assert _app_folder_name(db, 7) == "alpha_name"


def test_a_name_without_a_date_never_takes_over_from_a_name_that_was_seen(tmp_path):
    # the alphabet no longer counts once a name has a date
    db = _account(tmp_path, 7, [("zeta_name", MARCH, APRIL)])
    assert creator_names.add_name(tmp_path, 7, "alpha_name") is True
    assert _dates(db) == {"zeta_name": (MARCH, APRIL), "alpha_name": NO_DATES}
    assert _folder_name(db, 7) == "zeta_name" == _app_folder_name(db, 7)


def test_add_with_an_older_date_keeps_the_folder_name(tmp_path):
    db = _account(tmp_path, 7, [("zeta_name", APRIL, APRIL)])
    assert creator_names.add_name(tmp_path, 7, "alpha_name", seen="2024-03-01T09:30:00Z") is True
    assert _dates(db) == {"zeta_name": (APRIL, APRIL), "alpha_name": (MARCH, MARCH)}
    assert _folder_name(db, 7) == "zeta_name" == _app_folder_name(db, 7)


def test_add_refuses_a_date_that_would_change_the_folder_name(tmp_path):
    db = _account(tmp_path, 7, [("alpha_name", MARCH, APRIL)])
    with pytest.raises(creator_names.FolderNameWouldChange) as refused:
        creator_names.add_name(tmp_path, 7, "zeta_name", seen=MAY)
    assert "from 'alpha_name' to 'zeta_name'" in str(refused.value)
    assert _dates(db) == {"alpha_name": (MARCH, APRIL)}

    assert creator_names.add_name(tmp_path, 7, "zeta_name", seen=MAY, force=True) is True
    assert _dates(db) == {"alpha_name": (MARCH, APRIL), "zeta_name": (MAY, MAY)}
    assert _folder_name(db, 7) == "zeta_name" == _app_folder_name(db, 7)


def test_a_date_for_a_name_already_recorded_is_refused_when_the_folder_would_change(tmp_path):
    # both names are from before the dates: the first to get one becomes the folder name
    db = _account(tmp_path, 7, ["alpha_name", "zeta_name"])
    with pytest.raises(creator_names.FolderNameWouldChange):
        creator_names.add_name(tmp_path, 7, "zeta_name", seen=MAY)
    assert _dates(db) == {"alpha_name": NO_DATES, "zeta_name": NO_DATES}

    # the name the folder already has can be given its date
    assert creator_names.add_name(tmp_path, 7, "alpha_name", seen=MARCH) is False
    assert _dates(db) == {"alpha_name": (MARCH, MARCH), "zeta_name": NO_DATES}
    assert _folder_name(db, 7) == "alpha_name" == _app_folder_name(db, 7)


def test_force_alone_does_not_choose_the_folder_name(tmp_path):
    # the folder name is a name with a date: a name without one, or with an older one,
    # doesn't take over, forced or not
    db = _account(tmp_path, 7, [("zeta_name", MARCH, APRIL)])
    creator_names.add_name(tmp_path, 7, "alpha_name", force=True)
    creator_names.add_name(tmp_path, 7, "beta_name", seen="2024-03-15", force=True)
    assert _folder_name(db, 7) == "zeta_name" == _app_folder_name(db, 7)

    # a date later than every other name's does, with --force
    with pytest.raises(creator_names.FolderNameWouldChange):
        creator_names.add_name(tmp_path, 7, "beta_name", seen=MAY)
    creator_names.add_name(tmp_path, 7, "beta_name", seen=MAY, force=True)
    assert _folder_name(db, 7) == "beta_name" == _app_folder_name(db, 7)

    # and the name stays: OF-Scraper dates the name it uses for a deleted account, so
    # no older date takes over afterwards
    _app_works_on(db, 7, "beta_name")
    assert _dates(db)["beta_name"][1] > MAY
    creator_names.add_name(tmp_path, 7, "alpha_name", seen=MAY, force=True)
    assert _folder_name(db, 7) == "beta_name" == _app_folder_name(db, 7)


def test_when_no_name_has_a_date_any_date_makes_a_name_the_folder_name(tmp_path):
    db = _account(tmp_path, 7, ["alpha_name", "zeta_name"])
    with pytest.raises(creator_names.FolderNameWouldChange):
        creator_names.add_name(tmp_path, 7, "zeta_name", seen="2020-01-01")
    creator_names.add_name(tmp_path, 7, "zeta_name", seen="2020-01-01", force=True)
    assert _folder_name(db, 7) == "zeta_name" == _app_folder_name(db, 7)


def test_the_placeholder_is_never_the_folder_name_beside_a_name(tmp_path):
    db = _account(tmp_path, 7, ["zeta_name"])
    for stand_in in creator_names.placeholder_names(7):
        assert creator_names.add_name(tmp_path, 7, stand_in, force=True) is True
    assert _folder_name(db, 7) == "zeta_name" == _app_folder_name(db, 7)


def test_a_date_widens_the_dates_a_name_has_and_never_narrows_them(tmp_path):
    db = _account(tmp_path, 7, [("a_name", MARCH, APRIL), ("old_name", None, "2023-01-05T10:00:00+00:00")])
    # between the two: nothing to change
    assert creator_names.add_name(tmp_path, 7, "a_name", seen="2024-03-15") is False
    assert _dates(db)["a_name"] == (MARCH, APRIL)
    # earlier than the first, then later than the last
    creator_names.add_name(tmp_path, 7, "a_name", seen="2024-02-01")
    creator_names.add_name(tmp_path, 7, "a_name", seen=MAY)
    assert _dates(db)["a_name"] == ("2024-02-01T00:00:00+00:00", MAY)
    # a name seen after the upgrade has no first date yet
    creator_names.add_name(tmp_path, 7, "old_name", seen="2022-06-01")
    assert _dates(db)["old_name"] == ("2022-06-01T00:00:00+00:00", "2023-01-05T10:00:00+00:00")


@pytest.mark.parametrize(
    "given, saved",
    [
        ("2024-03-01", "2024-03-01T00:00:00+00:00"),
        ("2024-03-01T09:30", MARCH),
        ("2024-03-01 09:30:00", MARCH),
        ("2024-03-01T09:30:00Z", MARCH),
        ("2024-03-01T11:30:00+02:00", MARCH),
        (" 2024-03-01T09:30:00.750+00:00 ", MARCH),
    ],
)
def test_a_date_is_saved_the_way_the_scraper_saves_one(given, saved):
    assert creator_names.parse_seen(given) == saved
    # the scraper's own text for that second
    assert saved == arrow.get(saved).floor("second").isoformat()


@pytest.fixture
def hours_from_utc():
    """The computer's own time zone is hours from UTC, so that a time read as local time
    would come out wrong. Set where it can be (not on Windows); elsewhere the test goes on
    only if the zone is already away from UTC."""
    can_set = hasattr(time, "tzset")
    before = os.environ.get("TZ")
    if can_set:
        # five hours ahead, given as an offset: that needs no zone files
        os.environ["TZ"] = "AHEAD-5"
        time.tzset()
    try:
        if not datetime.datetime.now().astimezone().utcoffset():
            pytest.skip("the time zone is UTC and can't be set here")
        yield
    finally:
        if can_set:
            if before is None:
                del os.environ["TZ"]
            else:
                os.environ["TZ"] = before
            time.tzset()


def test_a_time_without_an_offset_is_utc_wherever_the_script_runs(hours_from_utc):
    assert creator_names.parse_seen("2024-03-01T09:30:00") == MARCH
    assert creator_names.parse_seen("2024-03-01") == "2024-03-01T00:00:00+00:00"


@pytest.mark.parametrize(
    "given",
    [
        "01/03/2024",
        "yesterday",
        "2024-13-01",
        "",
        "2024-03",
        # dates the calendar has, which their offset takes out of it in UTC
        "0001-01-01T00:00:00+05:00",
        "9999-12-31T23:59:59-05:00",
    ],
)
def test_text_that_is_not_a_date_is_refused(tmp_path, capsys, given):
    db = _account(tmp_path, 7, ["zeta_name"])
    with pytest.raises(ValueError, match="isn't a date"):
        creator_names.add_name(tmp_path, 7, "another_name", seen=given)
    # said in one line, and nothing is changed
    args = ["--data-dir", str(tmp_path), "--add", "7", "another_name", "--seen", given]
    assert creator_names.main(args) == 1
    assert capsys.readouterr().err.startswith(f"--seen: {given!r} isn't a date.")
    assert _names(db) == ["zeta_name"]


def test_a_date_in_the_future_is_refused(tmp_path, monkeypatch):
    db = _account(tmp_path, 7, ["zeta_name"])
    now = datetime.datetime(2024, 5, 1, 12, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(creator_names, "_now", lambda: now)
    for given in ("2024-05-03", "2024-05-02T12:00:01", "9999-12-31T23:59:59"):
        with pytest.raises(ValueError, match="is more than a day in the future"):
            creator_names.add_name(tmp_path, 7, "zeta_name", seen=given)
    assert _dates(db) == {"zeta_name": NO_DATES}
    # two days before is fine
    creator_names.add_name(tmp_path, 7, "zeta_name", seen="2024-04-29")
    assert _dates(db) == {"zeta_name": ("2024-04-29T00:00:00+00:00",) * 2}


def test_a_date_up_to_a_day_ahead_is_taken(tmp_path, monkeypatch):
    # late in the evening in UTC: for someone ten hours ahead it is already the 2nd, and
    # the date they give is still to come in UTC
    db = _account(tmp_path, 7, ["zeta_name"])
    now = datetime.datetime(2024, 5, 1, 22, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(creator_names, "_now", lambda: now)

    creator_names.add_name(tmp_path, 7, "zeta_name", seen="2024-05-02")
    assert _dates(db) == {"zeta_name": ("2024-05-02T00:00:00+00:00",) * 2}

    # a day ahead to the second, and no further
    creator_names.add_name(tmp_path, 7, "zeta_name", seen="2024-05-02T22:00:00")
    assert _dates(db)["zeta_name"][1] == "2024-05-02T22:00:00+00:00"
    with pytest.raises(ValueError, match="more than a day in the future"):
        creator_names.add_name(tmp_path, 7, "zeta_name", seen="2024-05-02T22:00:01")


@pytest.mark.parametrize("form", [0, 1], ids=["the placeholder", "with the id"])
def test_the_placeholder_is_not_given_a_date(tmp_path, capsys, form):
    stand_in = creator_names.placeholder_names(7)[form]
    db = _account(tmp_path, 7, [("zeta_name", MARCH, APRIL), stand_in])
    args = ["--data-dir", str(tmp_path), "--add", "7", stand_in]

    # one that is recorded, and one that would be new
    for account in (7, 8):
        if account == 8:
            _account(tmp_path, 8, ["a_name"])
            args[3], args[4] = "8", creator_names.placeholder_names(8)[form]
        assert creator_names.main(args + ["--seen", "2024-03-01", "--force"]) == 1
        said = capsys.readouterr().err
        assert said.startswith(f"--seen: {args[4]!r} is the placeholder")
        assert "never has a date" in said

    assert _dates(db) == {"zeta_name": (MARCH, APRIL), stand_in: NO_DATES}
    assert _names(tmp_path / "8" / "user_data.db") == ["a_name"]
    # another account's placeholder with the id is a name like any other here
    if form == 1:
        assert creator_names.add_name(tmp_path, 8, stand_in, seen=MARCH, force=True) is True


def test_a_database_from_before_the_dates_takes_a_name_but_no_date(tmp_path):
    db = _account(tmp_path, 7, ["alpha_name"], dates=False)
    with pytest.raises(ValueError, match="doesn't keep dates yet"):
        creator_names.add_name(tmp_path, 7, "zeta_name", seen=MARCH)
    assert _names(db) == ["alpha_name"]

    assert creator_names.add_name(tmp_path, 7, "zeta_name") is True
    assert _names(db) == ["alpha_name", "zeta_name"]
    with pytest.raises(creator_names.FolderNameWouldChange):
        creator_names.add_name(tmp_path, 7, "Alpha_name")
    assert _app_folder_name(db, 7) == "alpha_name"


@pytest.mark.parametrize("model_id, name", [("abc", "name"), ("7", ""), ("7", "   ")])
def test_add_refuses_a_bad_id_or_a_blank_name(tmp_path, model_id, name):
    db = _account(tmp_path, 7, ["zeta_name"])
    (tmp_path / "abc").mkdir()
    with pytest.raises(ValueError):
        creator_names.add_name(tmp_path, model_id, name)
    assert _names(db) == ["zeta_name"]


def test_add_refuses_an_unknown_account(tmp_path):
    with pytest.raises(FileNotFoundError):
        creator_names.add_name(tmp_path, 99, "name")


def test_skips_databases_without_the_tables(tmp_path):
    (tmp_path / "5").mkdir()
    with contextlib.closing(sqlite3.connect(tmp_path / "5" / "user_data.db")):
        pass
    _account(tmp_path, 6, ["a", "b"])
    assert [r[0] for r in creator_names.select(tmp_path)] == ["6"]


def test_cli_lists_and_writes_csv(tmp_path, capsys):
    data = tmp_path / "data"
    _account(data, 1, ["current_name", "old_name"], media=2)
    out_csv = tmp_path / "names.csv"
    assert creator_names.main(["--data-dir", str(data), "--csv", str(out_csv)]) == 0
    out = capsys.readouterr().out
    assert "current_name   also known as: old_name" in out
    assert "folder if deleted: current_name" in out
    with open(out_csv, newline="", encoding="utf-8") as fh:
        assert list(csv.reader(fh))[1] == [
            "1", "2", "current_name", "old_name", "current_name", " | ", " | ",
        ]


def test_cli_lists_the_days_a_name_was_seen_on(tmp_path, capsys):
    data = tmp_path / "data"
    _account(
        data,
        1,
        [
            ("old_name", MARCH, APRIL),
            ("current_name", MAY, MAY),
            ("seen_since", None, APRIL),
            ("by_hand", MARCH, None),
            "undated_name",
        ],
        media=2,
    )
    out_csv = tmp_path / "names.csv"

    assert creator_names.main(["--data-dir", str(data), "--csv", str(out_csv)]) == 0

    assert capsys.readouterr().out.splitlines()[0] == (
        "         1       2 media  old_name (seen 2024-03-01 to 2024-04-01)"
        "   also known as: current_name (seen 2024-05-01),"
        " seen_since (last seen 2024-04-01), by_hand (first seen 2024-03-01), undated_name"
        "   folder if deleted: current_name"
    )
    with open(out_csv, newline="", encoding="utf-8") as fh:
        header, row = list(csv.reader(fh))
    assert header == [
        "model_id", "media", "first_recorded_name", "other_names", "folder_if_deleted",
        "first_seen", "last_seen",
    ]
    assert row == [
        "1",
        "2",
        "old_name",
        "current_name | seen_since | by_hand | undated_name",
        "current_name",
        f"{MARCH} | {MAY} |  | {MARCH} | ",
        f"{APRIL} | {MAY} | {APRIL} |  | ",
    ]


def test_cli_says_it_works_on_sqlite_files_while_postgresql_is_on(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(URL_KEY, URL)
    _account(tmp_path, 1, ["current_name", "old_name"], media=2)
    path = list(sys.path)
    assert creator_names.main(["--data-dir", str(tmp_path)]) == 0
    said = capsys.readouterr()
    assert said.err.startswith("warning: PostgreSQL is on (OFSC_DATABASE_URL is set)")
    assert "creator_names.py works on the user_data.db files" in said.err
    assert "password" not in said.err
    # the listing still comes
    assert "current_name   also known as: old_name" in said.out
    assert sys.path == path


def test_cli_says_nothing_about_postgresql_while_it_is_off(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(URL_KEY, raising=False)
    _account(tmp_path, 1, ["current_name", "old_name"], media=2)
    assert creator_names.main(["--data-dir", str(tmp_path)]) == 0
    said = capsys.readouterr()
    assert said.err == ""
    assert "current_name   also known as: old_name" in said.out


def test_run_as_a_script_it_says_so_with_nothing_put_on_pythons_path(tmp_path):
    """As a user starts it, from the repo root: the scraper beside the script
    is found without PYTHONPATH, installed or not."""
    _account(tmp_path, 1, ["current_name", "old_name"], media=2)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "scripts/creator_names.py", "--data-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**env, URL_KEY: URL},
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr.startswith("warning: PostgreSQL is on (OFSC_DATABASE_URL is set)")
    assert "creator_names.py works on the user_data.db files" in result.stderr
    assert "current_name   also known as: old_name" in result.stdout


def test_cli_add_reports_a_missing_account(tmp_path, capsys):
    assert creator_names.main(["--data-dir", str(tmp_path), "--add", "3", "name"]) == 1
    assert "no OF-Scraper database" in capsys.readouterr().err


def test_cli_add_refuses_a_folder_change_without_force(tmp_path, capsys):
    db = _account(tmp_path, 7, ["zeta_name"])
    args = ["--data-dir", str(tmp_path), "--add", "7", "alpha_name"]
    assert creator_names.main(args) == 1
    assert "pass --force" in capsys.readouterr().err
    assert creator_names.main(args + ["--force"]) == 0
    assert _app_folder_name(db, 7) == "alpha_name"


def test_cli_add_takes_a_date(tmp_path, capsys):
    db = _account(tmp_path, 7, [("zeta_name", APRIL, APRIL)])
    args = ["--data-dir", str(tmp_path), "--add", "7", "alpha_name", "--seen"]

    assert creator_names.main(args + ["2024-03-01"]) == 0
    assert capsys.readouterr().out == "Added: alpha_name -> 7, seen 2024-03-01T00:00:00+00:00\n"
    assert _dates(db)["alpha_name"] == ("2024-03-01T00:00:00+00:00",) * 2

    # a newer date would change the folder name
    assert creator_names.main(args + ["2024-05-01"]) == 1
    assert "pass --force" in capsys.readouterr().err
    assert creator_names.main(args + ["2024-05-01", "--force"]) == 0
    assert "Already recorded: alpha_name -> 7, seen 2024-05-01" in capsys.readouterr().out
    assert _folder_name(db, 7) == "alpha_name" == _app_folder_name(db, 7)


def test_cli_says_what_is_wrong_with_a_date(tmp_path, capsys):
    db = _account(tmp_path, 7, ["zeta_name"])
    args = ["--data-dir", str(tmp_path), "--add", "7", "zeta_name", "--seen", "1 March"]

    assert creator_names.main(args) == 1

    said = capsys.readouterr().err
    assert "--seen: '1 March' isn't a date" in said
    assert "2024-03-01" in said
    assert _dates(db) == {"zeta_name": NO_DATES}


def test_cli_wants_a_name_for_a_date(tmp_path, capsys):
    _account(tmp_path, 7, ["zeta_name", "alpha_name"])

    assert creator_names.main(["--data-dir", str(tmp_path), "--seen", "2024-03-01"]) == 1

    captured = capsys.readouterr()
    assert "--seen goes with --add" in captured.err
    assert captured.out == ""
