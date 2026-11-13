import contextlib
import csv
import importlib.util
import pathlib
import sqlite3

import pytest

_spec = importlib.util.spec_from_file_location(
    "creator_names",
    pathlib.Path(__file__).resolve().parents[1] / "scripts" / "creator_names.py",
)
creator_names = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(creator_names)

# Same constraint OF-Scraper creates (ofscraper/db/operations_/profile.py)
PROFILES = """
CREATE TABLE profiles (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username VARCHAR NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (user_id, username)
)
"""


def _account(data_dir, model_id, names, media=0):
    db = data_dir / str(model_id) / "user_data.db"
    db.parent.mkdir(parents=True)
    with contextlib.closing(sqlite3.connect(db)) as con:
        con.execute(PROFILES)
        con.execute("CREATE TABLE medias (id INTEGER PRIMARY KEY, media_id INTEGER)")
        con.executemany(
            "INSERT INTO profiles (user_id, username) VALUES (?, ?)",
            [(model_id, n) for n in names],
        )
        con.executemany("INSERT INTO medias (media_id) VALUES (?)", [(i,) for i in range(media)])
        con.commit()
    return db


def _names(db):
    with contextlib.closing(sqlite3.connect(db)) as con:
        return [r[0] for r in con.execute("SELECT username FROM profiles ORDER BY id")]


def _app_folder_name(db, model_id):
    # the exact query OF-Scraper runs for a deleted account (get_profile_info)
    with contextlib.closing(sqlite3.connect(db)) as con:
        return con.execute(
            "SELECT username FROM profiles where user_id=(?)", (model_id,)
        ).fetchone()[0]


def test_lists_only_accounts_with_several_names(tmp_path):
    _account(tmp_path, 1, ["current_name", "old_name"], media=3)
    _account(tmp_path, 2, ["only_name"])
    rows = creator_names.select(tmp_path)
    assert rows == [("1", ["current_name", "old_name"], 3, "current_name")]
    assert len(creator_names.select(tmp_path, show_all=True)) == 2


def test_listing_shows_the_folder_name_the_app_uses(tmp_path):
    # recorded first isn't what the app picks: its query returns names alphabetically
    db = _account(tmp_path, 1, ["zeta_name", "alpha_name"])
    (row,) = creator_names.select(tmp_path)
    assert row[1][0] == "zeta_name"
    assert row[3] == "alpha_name" == _app_folder_name(db, 1)


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
    assert _app_folder_name(db, 7) == "alpha_name"


def test_add_refuses_a_name_that_would_change_the_folder_name(tmp_path):
    # OF-Scraper names a deleted account's folder after the first row of its query,
    # which is alphabetical; alpha_name would take over from zeta_name
    db = _account(tmp_path, 7, ["zeta_name"])
    with pytest.raises(creator_names.FolderNameWouldChange):
        creator_names.add_name(tmp_path, 7, "alpha_name")
    assert _names(db) == ["zeta_name"]
    assert _app_folder_name(db, 7) == "zeta_name"


def test_add_with_force_changes_the_folder_name(tmp_path):
    db = _account(tmp_path, 7, ["zeta_name"])
    assert creator_names.add_name(tmp_path, 7, "alpha_name", force=True) is True
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
        assert list(csv.reader(fh))[1] == ["1", "2", "current_name", "old_name", "current_name"]


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
