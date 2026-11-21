"""Writing what PostgreSQL holds back to user_data.db files (#632): everything
the command does short of talking to a server, which
test_postgres_export_live.py does.

The stand-in database hands out rows the way the scraper's engine does: a
yes or no as 1 or 0, a date as ISO text in UTC. What it holds is what the
import sends for a folder of files.
"""

import asyncio
import contextlib
import os
import sqlite3
import threading
import time
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.postgres_export as exporter
import ofscraper.commands.postgres_import as importer
import ofscraper.db.operations as operations
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.others as others
import ofscraper.db.operations_.profile as profile
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.postgres as postgres
import ofscraper.db.transition as transition
import ofscraper.utils.settings as settings
from ofscraper.db.difference import ALL_FLAGS, get_group_difference
from ofscraper.db.transition import modify_tables
from test.db_scenario import ONE, TABLES, TWO, check, plain, scenario, table_rows
from test.import_files import current_file, file_2023, sql
from test.test_postgres_import import Target as ImportTarget

DATABASE = exporter.DATABASE


class ServerError(Exception):
    """What the stand-in's driver raises."""


class Database:
    """Holds {(site, table): [{column: value}]}."""

    errors = (ServerError,)

    def __init__(self, kept=None, flags=None):
        self.kept = kept or {}
        self.had = flags or {}
        self.asked = []
        self.opened = 0
        self.closed = 0

    def check(self):
        return "18.0"

    def open(self):
        self.opened += 1

    def close(self):
        self.closed += 1

    def held(self, site):
        found = {}
        for (name, table), rows in self.kept.items():
            column = exporter.CREATOR_COLUMN.get(table, "model_id")
            for row in rows if name == site else ():
                counts = found.setdefault(row[column], {})
                counts[table] = counts.get(table, 0) + 1
        return found

    def flags(self, site):
        return set(self.had.get(site, ALL_FLAGS))

    def rows(self, site, table, columns, creator):
        self.asked.append((site, table, creator))
        column = exporter.CREATOR_COLUMN.get(table, "model_id")
        # oldest first, where the rows say which that is
        return [
            tuple(row.get(name) for name in columns)
            for row in sorted(
                self.kept.get((site, table), []), key=lambda row: row.get("id", 0)
            )
            if row[column] == creator
        ]


def as_read(table, column, value):
    """A value the import sent, as the engine hands it back: PostgreSQL keeps
    a date as a moment and gives it in UTC, and the engine gives a yes or no
    as 1 or 0 and a whole number in a text id column as a number. The real
    server's answer is checked in test_postgres_export_live.py."""
    kind = postgres.COLUMN_TYPES[table][column]
    if value is None:
        return None
    if kind == "BOOLEAN":
        return int(value)
    if kind == "TIMESTAMPTZ":
        moment = arrow.get(value).to("UTC")
        part = f".{moment.microsecond:06d}".rstrip("0") if moment.microsecond else ""
        return postgres.iso(f"{moment.format('YYYY-MM-DD HH:mm:ss')}{part}+00")
    if kind == "NUMERIC":
        return postgres.number(str(value))
    if column in postgres.LOOSE_IDS and postgres._WHOLE_NUMBER.fullmatch(str(value)):
        return int(value)
    return value


def brought_in(folder):
    """What the import sends for the files under `folder`."""
    target = ImportTarget()
    lines = []
    code = importer.run(folder, target=target, apply=True, out=lines.append)
    assert code == 0, "\n".join(lines)
    return target.kept


def holding(folder):
    """A database that holds the files under `folder`."""
    return Database(
        {
            (site, table): [
                {column: as_read(table, column, value) for column, value in row.items()}
                for row in rows
            ]
            for (site, table), rows in brought_in(folder).items()
        }
    )


def two_creators(tmp_path):
    folder = tmp_path / "data"
    current_file(folder / "111" / DATABASE, 111)
    current_file(folder / "222" / DATABASE, 222, name="another_creator")
    return holding(folder)


def run(folder, target=None, **kwargs):
    lines = []
    code = exporter.run(folder, target=target, out=lines.append, **kwargs)
    return code, "\n".join(lines)


def files(folder):
    """Every file under `folder`, by its path from there."""
    return sorted(
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file()
    )


def dump(path):
    """Every row of every table of a file, each value with its type."""
    tables = sql(
        path,
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )
    return {
        table: sorted(
            [(type(value).__name__, value) for value in row]
            for row in sql(path, f"SELECT * FROM {table}")
        )
        for (table,) in tables
    }


def layout(path):
    """The tables and indexes of a file, as they were made."""
    return sql(path, "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name")


def canonical(path):
    """current_file's rows with every value as the scraper saves it today: a
    date as ISO text with its offset, and nothing where there is no date."""
    sql(path, "UPDATE medias SET created_at = NULL WHERE created_at = ''")
    sql(
        path,
        "UPDATE medias SET posted_at = '2024-03-01T09:30:00+00:00'"
        " WHERE posted_at = 1709285400",
    )
    sql(
        path,
        "UPDATE posts SET created_at = '2024-03-01T09:30:00+00:00' WHERE post_id = 10",
    )
    return path


def moments(kept):
    """What an import sent, with every date as its moment in UTC."""
    return {
        key: [
            {
                column: (
                    arrow.get(value).to("UTC").isoformat()
                    if value is not None
                    and postgres.COLUMN_TYPES[key[1]][column] == "TIMESTAMPTZ"
                    else value
                )
                for column, value in row.items()
            }
            for row in rows
        ]
        for key, rows in kept.items()
    }


def scan_tables(saved):
    """What a run of db_scenario saved, as {table: rows}."""
    return {
        table: saved[f"table {table}"] for table in TABLES if table != "schema_flags"
    }


def each_creator_has_their_rows(out, saved):
    """Each creator's file under `out` holds their rows of every table that
    db_scenario saved, as the scraper reads them."""
    for creator in (ONE, TWO):
        path = out / str(creator) / DATABASE
        for table, rows in scan_tables(saved).items():
            column = exporter.CREATOR_COLUMN.get(table, "model_id")
            expected = [dict(row) for row in rows if row[column] == creator]
            in_file = table_rows(table, read_only=True, db_path=path)
            # a row's id is its place in line among the creator's own rows
            for found in (expected, in_file):
                found.sort(key=lambda row: row["id"])
                for place, row in enumerate(found, start=1):
                    row["id"] = place
            assert plain(in_file) == plain(expected), (creator, table)
        assert others.get_schema_changes(db_path=path) == set(ALL_FLAGS)


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


# --- the preview ---


def test_each_creator_has_a_file_planned_under_their_id(tmp_path):
    planned = exporter.plan(
        tmp_path, "onlyfans", {222: {"posts": 2}, 111: {"medias": 3, "profiles": 1}}
    )

    assert [(file.creator, file.path) for file in planned] == [
        (111, tmp_path / "111" / DATABASE),
        (222, tmp_path / "222" / DATABASE),
    ]
    assert planned[0].counts == {"medias": 3, "profiles": 1}
    assert [file.problems for file in planned] == [[], []]


def test_without_apply_nothing_is_written(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"

    code, said = run(out, database)

    assert code == 0, said
    assert "onlyfans: 2 creators" in said
    assert "medias             6 rows" in said
    assert "profiles           2 rows" in said
    assert f"Nothing was written. Run again with --apply to write 2 files under {out}." in said
    # not even the folder
    assert not out.exists()
    assert database.asked == []
    assert (database.opened, database.closed) == (1, 1)


def test_it_needs_a_database(tmp_path):
    code, said = run(tmp_path / "out", apply=True)

    assert code == 2
    assert "OFSC_DATABASE_URL isn't set" in said
    assert not (tmp_path / "out").exists()


def test_a_folder_that_is_a_file_is_said_so(tmp_path):
    (tmp_path / "out").write_text("mine")

    code, said = run(tmp_path / "out", Database(), apply=True)

    assert code == 2
    assert "isn't a folder" in said
    assert (tmp_path / "out").read_text() == "mine"


def test_a_database_with_nothing_in_it_is_said_so(tmp_path):
    code, said = run(tmp_path / "out", Database(), apply=True)
    assert code == 0
    assert "PostgreSQL has no rows." in said

    code, said = run(tmp_path / "out", Database(), apply=True, site="fansly")
    assert code == 0
    assert said.endswith("PostgreSQL has no rows for fansly.")
    assert not (tmp_path / "out").exists()


def test_the_site_that_has_the_rows_is_named_when_another_is_asked_for(tmp_path):
    code, said = run(tmp_path / "out", two_creators(tmp_path), apply=True, site="fansly")

    assert code == 0
    assert "PostgreSQL has no rows for fansly. It has rows for onlyfans." in said
    assert not (tmp_path / "out").exists()


def test_a_folder_that_cant_be_made_is_said_so(tmp_path):
    database = two_creators(tmp_path)
    (tmp_path / "mine").write_text("mine")
    out = tmp_path / "mine" / "out"

    code, said = run(out, database, apply=True)

    assert code == 1
    assert f"Nothing was written. {out} couldn't be made (" in said
    assert (tmp_path / "mine").read_text() == "mine"
    assert database.closed == 1


def test_a_database_that_cant_be_opened_is_closed_again(tmp_path):
    database = two_creators(tmp_path)

    def refuses():
        raise ServerError("the server said no")

    database.open = refuses

    code, said = run(tmp_path / "out", database, apply=True)

    assert code == 1
    assert "Nothing was written. the server said no" in said
    assert database.closed == 1


# --- the files ---


def test_with_apply_each_creator_gets_their_rows(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert code == 0, said
    assert "onlyfans: 2 files written, 20 rows." in said
    assert "PostgreSQL was only read" in said
    # the files, and nothing beside them
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]
    path = out / "222" / DATABASE
    assert sql(path, "SELECT user_id, username FROM profiles") == [
        (222, "another_creator")
    ]
    assert sql(path, "SELECT model_id FROM models") == [(222,)]
    assert sql(path, "SELECT DISTINCT model_id FROM medias") == [(222,)]
    # oldest first, as they were saved
    assert sql(path, "SELECT id, post_id FROM posts ORDER BY id") == [(1, 20), (2, 10)]
    assert sql(
        path,
        "SELECT text, price, paid, archived, pinned, created_at, is_deleted"
        " FROM posts WHERE post_id = 10",
    ) == [("first\nline two\ttab \\ slash", 9.99, 1, 1, 0, "2024-03-01T09:30:00+00:00", 1)]
    assert sql(
        path,
        "SELECT media_id, post_id, size, downloaded, created_at, skip_permanent"
        " FROM medias ORDER BY id",
    ) == [
        (1, 10, 2**40, 1, "2024-03-01T09:30:00+00:00", None),
        (2, 10, None, 0, None, 1),
        (1, 20, 5, 1, "2024-03-02T10:00:00+00:00", None),
    ]
    assert sql(path, "SELECT label_id, name, post_id FROM labels") == [
        (900, "favourites", 10)
    ]
    assert (database.opened, database.closed) == (1, 1)


def test_a_file_is_one_the_scraper_would_have_made(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    assert run(out, database, apply=True)[0] == 0
    path = out / "111" / DATABASE
    made = tmp_path / "made" / DATABASE
    made.parent.mkdir()

    async def as_a_scan_makes_one():
        await operations.create_tables(db_path=made)
        await modify_tables(db_path=made, new_db=True)

    asyncio.run(as_a_scan_makes_one())

    assert layout(path) == layout(made)
    assert sql(path, "SELECT * FROM schema_flags ORDER BY flag_name") == sql(
        made, "SELECT * FROM schema_flags ORDER BY flag_name"
    )
    assert sql(path, "PRAGMA journal_mode") == sql(made, "PRAGMA journal_mode")
    # no upgrade step is left for the scraper to run, and it reads the rows
    assert others.get_schema_changes(db_path=path) == set(ALL_FLAGS)
    assert get_group_difference(db_path=path) == set()
    assert others.get_site_flag(db_path=path) is None
    assert profile.get_single_model_via_profile(db_path=path) == 111
    assert set(
        media.get_media_ids_downloaded_model_sync(
            model_id=111, username="a_creator", db_path=path
        )
    ) == {1}
    # nothing was left beside it by those reads either
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]


def test_a_file_the_scraper_wrote_comes_back_row_for_row(tmp_path):
    folder = tmp_path / "data"
    original = canonical(current_file(folder / "111" / DATABASE, 111))
    out = tmp_path / "out"

    code, said = run(out, holding(folder), apply=True)

    assert code == 0, said
    # every table, every value and its type, each row's own id too
    assert dump(out / "111" / DATABASE) == dump(original)
    assert layout(out / "111" / DATABASE) == layout(original)


def test_what_was_brought_in_comes_back_as_the_import_carried_it(tmp_path):
    folder = tmp_path / "data"
    path = current_file(folder / "111" / DATABASE, 111)
    # values the import reads its own way: a date with another offset, a date
    # as a number of seconds, a yes as text, a number as text, a profile
    # picture's ids and a label with a word for an id
    picture = "0123456789abcdef0123456789abcdef"
    sql(
        path,
        "INSERT INTO posts (post_id, text, price, paid, created_at, model_id)"
        " VALUES (60, '', '15', 'true', '2024-03-05T08:30:00+02:00', 111)",
    )
    sql(
        path,
        "INSERT INTO medias (media_id, post_id, api_type, downloaded, posted_at,"
        f" model_id) VALUES ('{picture}', '{picture[::-1]}', 'Profile', 1,"
        " 1709285400.5, 111)",
    )
    sql(
        path,
        "INSERT INTO labels (label_id, name, type, post_id, model_id)"
        " VALUES ('archived', 'Archived', 'archived', 10, 111)",
    )
    file_2023(folder / "222" / DATABASE, 222, name="an_old_creator")
    first = brought_in(folder)
    out = tmp_path / "out"

    code, said = run(out, holding(folder), apply=True)

    assert code == 0, said
    # brought in again, the new files give what the old ones gave
    assert moments(brought_in(out)) == moments(first)
    # the same moment, written in UTC
    assert sql(
        out / "111" / DATABASE,
        "SELECT text, price, paid, created_at FROM posts WHERE post_id = 60",
    ) == [("", 15, 1, "2024-03-05T06:30:00+00:00")]
    assert sql(
        out / "111" / DATABASE,
        "SELECT media_id, post_id, posted_at FROM medias WHERE api_type = 'Profile'",
    ) == [(picture, picture[::-1], "2024-03-01T09:30:00.5+00:00")]
    # the old file's rows, at today's layout
    assert sql(out / "222" / DATABASE, "SELECT post_id, model_id, paid FROM posts") == [
        (10, 222, 0),
        (11, 222, 1),
    ]


def test_what_a_scan_saved_comes_out_as_the_scraper_reads_it(tmp_path, monkeypatch):
    # two creators, saved through the functions a scan uses. Into one SQLite
    # file here: test_db_postgres_live checks PostgreSQL reads the same
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: tmp_path / "shared" / DATABASE,
    )
    saved = asyncio.run(scenario())
    check(saved)
    database = Database(
        {("onlyfans", table): rows for table, rows in scan_tables(saved).items()}
    )
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert code == 0, said
    assert files(out) == [f"{ONE}/{DATABASE}", f"{TWO}/{DATABASE}"]
    each_creator_has_their_rows(out, saved)


def test_a_fansly_file_says_which_site_it_is_for(tmp_path):
    folder = tmp_path / "data"
    current_file(folder / "111" / DATABASE, 111, site="fansly")
    out = tmp_path / "out"

    code, said = run(out, holding(folder), apply=True)

    assert code == 0, said
    assert "fansly: 1 file written" in said
    assert others.get_site_flag(db_path=out / "111" / DATABASE) == "fansly"
    # and the import takes it for that site's
    assert {site for site, table in brought_in(out)} == {"fansly"}


def test_two_sites_are_written_one_at_a_time(tmp_path):
    folder = tmp_path / "data"
    current_file(folder / "111" / DATABASE, 111)
    current_file(folder / "Fansly" / "111" / DATABASE, 111, site="fansly")
    database = holding(folder)
    out = tmp_path / "out"

    # the same id is a creator of its own on each site
    code, said = run(out, database, apply=True)
    assert code == 2
    assert "PostgreSQL has rows for fansly and onlyfans" in said
    assert "--site" in said
    assert not out.exists()

    code, said = run(out / "of", database, apply=True, site="onlyfans")
    assert code == 0, said
    code, said = run(out / "fansly", database, apply=True, site="fansly")
    assert code == 0, said
    assert files(out) == [f"fansly/111/{DATABASE}", f"of/111/{DATABASE}"]
    assert others.get_site_flag(db_path=out / "of" / "111" / DATABASE) is None
    assert others.get_site_flag(db_path=out / "fansly" / "111" / DATABASE) == "fansly"


def test_a_creator_with_only_a_name_gets_a_file(tmp_path):
    # a scan saves the creator's name before anything else
    database = Database(
        {
            ("onlyfans", "profiles"): [
                {"user_id": 333, "username": "old_name"},
                {"user_id": 333, "username": "new_name"},
            ]
        }
    )
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert code == 0, said
    path = out / "333" / DATABASE
    assert sql(path, "SELECT user_id, username FROM profiles ORDER BY id") == [
        (333, "old_name"),
        (333, "new_name"),
    ]
    assert sql(path, "SELECT model_id FROM models") == [(333,)]


# --- a file that is already there ---


def test_a_file_that_is_already_there_is_never_changed(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    theirs = out / "111" / DATABASE
    theirs.parent.mkdir(parents=True)
    theirs.write_bytes(b"theirs")

    code, said = run(out, database)
    assert code == 1
    assert "onlyfans: 1 creator" in said
    assert "1 creator is left out:" in said
    assert f"  {theirs}\n    - {exporter.ALREADY_THERE}" in said
    assert "run this again with another folder" in said
    assert "Run again with --apply to write 1 file under" in said

    code, said = run(out, database, apply=True)

    # written, but not everything: the exit code says so
    assert code == 1
    assert f"  {theirs}\n    - {exporter.ALREADY_THERE}" in said
    assert "onlyfans: 1 file written" in said
    assert theirs.read_bytes() == b"theirs"
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]
    # the creator's rows weren't even read
    assert {creator for _, _, creator in database.asked} == {222}


def test_another_folder_gets_a_left_out_creators_rows_out(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    assert run(out, database, apply=True)[0] == 0
    before = {name: (out / name).read_bytes() for name in files(out)}

    # a second run changes nothing
    code, said = run(out, database, apply=True)
    assert code == 1
    assert "2 creators are left out:" in said
    assert "There is nothing to write." in said
    assert {name: (out / name).read_bytes() for name in files(out)} == before

    code, said = run(tmp_path / "elsewhere", database, apply=True)
    assert code == 0, said
    assert files(tmp_path / "elsewhere") == [f"111/{DATABASE}", f"222/{DATABASE}"]


@pytest.mark.parametrize("suffix", ["-wal", "-journal"])
def test_what_sqlite_kept_beside_a_database_that_has_gone_is_in_the_way(
    tmp_path, suffix
):
    # SQLite reads a -wal or -journal file into the database it sits beside
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    (out / "111").mkdir(parents=True)
    (out / "111" / f"{DATABASE}{suffix}").write_bytes(b"left behind")

    code, said = run(out, database, apply=True)

    assert code == 1
    assert f"{DATABASE}{suffix} is there without its database" in said
    assert files(out) == [f"111/{DATABASE}{suffix}", f"222/{DATABASE}"]
    assert (out / "111" / f"{DATABASE}{suffix}").read_bytes() == b"left behind"
    assert {creator for _, _, creator in database.asked} == {222}


def test_a_link_that_leads_nowhere_is_in_the_way_too(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    (out / "111").mkdir(parents=True)
    try:
        (out / "111" / DATABASE).symlink_to(tmp_path / "nothing")
    except OSError:
        pytest.skip("links can't be made here")

    code, said = run(out, database, apply=True)

    assert code == 1
    assert exporter.ALREADY_THERE in said
    assert (out / "111" / DATABASE).is_symlink()


# --- a file is whole or isn't there ---


def test_a_file_has_its_name_only_once_it_is_whole(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    seen = []
    rows = database.rows

    def watched(site, table, columns, creator):
        seen.append(files(out / str(creator)))
        return rows(site, table, columns, creator)

    database.rows = watched

    code, said = run(out, database, apply=True)

    assert code == 0, said
    assert len(seen) == 18  # nine tables, two creators
    for there in seen:
        # being made under another name, beside its place
        assert DATABASE not in there
        assert [name for name in there if name.endswith(exporter.PARTIAL)]
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]


def test_a_run_that_stops_part_way_leaves_no_half_made_file(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    rows = database.rows

    def goes_away(site, table, columns, creator):
        if creator == 222 and table == "posts":
            raise ServerError("the server went away")
        return rows(site, table, columns, creator)

    database.rows = goes_away

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "Stopped. the server went away" in said
    assert "1 file had been written by then" in said
    # the first file is whole, and of the second there is nothing
    assert files(out) == [f"111/{DATABASE}"]
    assert [path.name for path in out.iterdir()] == ["111"]
    assert database.closed == 1

    database.rows = rows
    code, said = run(out, database, apply=True)

    assert code == 1
    assert "1 creator is left out:" in said
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]


def test_a_stop_before_any_file_says_nothing_was_written(tmp_path, monkeypatch):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setenv(postgres.URL_KEY, "postgresql://me:s3cret-word@localhost/db")

    def refuses(site, table, columns, creator):
        raise ServerError("no such column\nDETAIL: for s3cret-word")

    database.rows = refuses

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "Nothing was written. no such column DETAIL: for {hidden}" in said
    assert "s3cret-word" not in said
    assert list(out.iterdir()) == []


def test_a_file_that_appears_meanwhile_is_left_as_it_is(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    theirs = out / "111" / DATABASE
    rows = database.rows

    def a_scraper_starts(site, table, columns, creator):
        if creator == 111 and not theirs.exists():
            theirs.write_bytes(b"theirs")
        return rows(site, table, columns, creator)

    database.rows = a_scraper_starts

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "1 file couldn't be written:" in said
    assert "a file appeared there while this ran, and was left as it is" in said
    assert theirs.read_bytes() == b"theirs"
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]


def no_second_names(source, target):
    """os.link on a disk without hard links: FAT, some network shares."""
    raise OSError("this disk has none")


def named(finished, name):
    """place(), and whether the file got the name."""
    try:
        exporter.place(finished, name)
    except exporter.Taken:
        return False
    return True


def test_a_finished_file_never_takes_another_files_name(tmp_path):
    finished = tmp_path / "finished"
    finished.write_bytes(b"new")

    assert named(finished, tmp_path / DATABASE)
    assert (tmp_path / DATABASE).read_bytes() == b"new"

    # the name it was made under is the caller's to remove
    finished.unlink()
    finished.write_bytes(b"newer")
    assert not named(finished, tmp_path / DATABASE)
    assert (tmp_path / DATABASE).read_bytes() == b"new"
    assert finished.read_bytes() == b"newer"


def test_on_a_disk_without_second_names_a_name_is_looked_for_first(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(os, "link", no_second_names)
    # a rename that replaces, as on every system but Windows
    monkeypatch.setattr(os, "rename", os.replace)
    finished = tmp_path / "finished"
    finished.write_bytes(b"new")

    # a name that is free is given
    assert named(finished, tmp_path / DATABASE)
    assert (tmp_path / DATABASE).read_bytes() == b"new"
    assert not finished.exists()

    # and one that is taken isn't
    finished.write_bytes(b"newer")
    assert not named(finished, tmp_path / DATABASE)
    assert (tmp_path / DATABASE).read_bytes() == b"new"
    assert finished.read_bytes() == b"newer"


def test_a_rename_that_refuses_a_taken_name_leaves_the_file_there(
    tmp_path, monkeypatch
):
    # without second names a file can take the name between the look and
    # the rename. Windows' rename then refuses, as here; another system's
    # replaces the file (see place)
    monkeypatch.setattr(os, "link", no_second_names)
    finished = tmp_path / "finished"
    finished.write_bytes(b"new")
    theirs = tmp_path / DATABASE

    def refuses(source, target):
        theirs.write_bytes(b"theirs")
        raise FileExistsError("the name is taken")

    monkeypatch.setattr(os, "rename", refuses)

    assert not named(finished, theirs)
    assert theirs.read_bytes() == b"theirs"
    assert finished.read_bytes() == b"new"


def test_a_disk_without_second_names_still_gets_its_files(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "link", no_second_names)
    out = tmp_path / "out"

    code, said = run(out, two_creators(tmp_path), apply=True)

    assert code == 0, said
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]
    assert sql(out / "111" / DATABASE, "SELECT COUNT(*) FROM medias") == [(3,)]


def test_one_file_that_cant_be_written_doesnt_stop_the_rest(tmp_path):
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    # where the creator's folder would go
    (out / "111").write_text("mine")

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "onlyfans: 1 file written" in said
    assert "1 file couldn't be written:" in said
    assert f"  {out / '111' / DATABASE}\n    - it couldn't be written (" in said
    assert files(out) == ["111", f"222/{DATABASE}"]
    assert (out / "111").read_text() == "mine"


def refused(tmp_path, spoil, why):
    """Two creators, one of them with something that stops their file: the
    other's is written, and of theirs nothing is left."""
    database = two_creators(tmp_path)
    spoil(database)
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "1 file couldn't be written:" in said
    assert why in said
    assert files(out) == [f"111/{DATABASE}"]
    assert [path.name for path in out.iterdir()] == ["111"]
    return said


def of(database, table, creator):
    return [
        row for row in database.kept["onlyfans", table] if row["model_id"] == creator
    ]


def test_a_value_sqlite_would_keep_differently_stops_that_file(tmp_path):
    # PostgreSQL keeps these ids as text; SQLite's column makes a number of
    # text that reads as one
    def spoil(database):
        of(database, "medias", 222)[1]["media_id"] = "007"

    said = refused(tmp_path, spoil, "medias row 2, media_id: SQLite keeps '007' as 7")
    # which value, and where it has to be changed
    assert (
        f"  {tmp_path / 'out' / '222' / DATABASE}\n"
        "    - medias row 2, media_id: SQLite keeps '007' as 7\n"
        f"    - {exporter.IN_POSTGRESQL}"
    ) in said


def test_a_number_sqlite_cant_keep_stops_that_file(tmp_path):
    def spoil(database):
        of(database, "posts", 222)[0]["price"] = float("nan")

    said = refused(tmp_path, spoil, "posts row 1, price: SQLite keeps nan as None")
    assert exporter.IN_POSTGRESQL in said


@pytest.mark.parametrize("number", [2**63, -(2**63) - 1, 2**70])
def test_a_number_too_large_for_sqlite_stops_that_file(tmp_path, number):
    def spoil(database):
        of(database, "posts", 222)[1]["price"] = number

    said = refused(
        tmp_path,
        spoil,
        f"posts row 2, price: {number} is too large a number for SQLite",
    )
    assert exporter.IN_POSTGRESQL in said


def test_the_largest_number_sqlite_keeps_is_written(tmp_path):
    database = two_creators(tmp_path)
    of(database, "posts", 222)[0]["price"] = 2**63 - 1
    of(database, "posts", 222)[1]["price"] = -(2**63)
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert code == 0, said
    assert sql(out / "222" / DATABASE, "SELECT price FROM posts ORDER BY id") == [
        (2**63 - 1,),
        (-(2**63),),
    ]


def test_a_value_the_import_would_refuse_stops_that_file(tmp_path):
    def spoil(database):
        of(database, "medias", 222)[0]["created_at"] = "infinity"

    said = refused(tmp_path, spoil, "1 value can't be stored")
    assert "medias row 1, created_at: 'infinity' isn't a date" in said
    assert exporter.IN_POSTGRESQL in said


# Rows for current_file's creator 111 that the import brings in, and why the
# file can't be written back (test_postgres_export_live.py asks a server too)
TAKEN_ON_THE_WAY_IN = [
    # a media id that isn't a whole number is text to PostgreSQL, which
    # keeps it as it is. SQLite's column makes a number of it again
    pytest.param(
        "INSERT INTO medias (media_id, post_id, model_id) VALUES (1.5, 77, 111)",
        "medias row 4, media_id: SQLite keeps '1.5' as 1.5",
        id="an id that isn't a whole number",
    ),
    # SQLite keeps a number this large as one with a fraction, and
    # PostgreSQL as the whole number it is
    pytest.param(
        "INSERT INTO posts (post_id, price, model_id) VALUES (77, 1e19, 111)",
        "posts row 3, price: 10000000000000000000 is too large a number for SQLite",
        id="a number too large",
    ),
]


@pytest.mark.parametrize("row, why", TAKEN_ON_THE_WAY_IN)
def test_a_value_the_import_took_can_stop_the_file_on_the_way_back(
    tmp_path, row, why
):
    folder = tmp_path / "data"
    sql(current_file(folder / "111" / DATABASE, 111), row)
    out = tmp_path / "out"

    code, said = run(out, holding(folder), apply=True)

    assert code == 1
    assert "onlyfans: 0 files written, 0 rows." in said
    assert (
        f"  {out / '111' / DATABASE}\n    - {why}\n    - {exporter.IN_POSTGRESQL}"
    ) in said
    assert list(out.iterdir()) == []


def test_rows_that_dont_all_arrive_are_not_kept(tmp_path):
    def spoil(database):
        rows = database.rows

        def loses_a_row(site, table, columns, creator):
            found = rows(site, table, columns, creator)
            return found[:-1] if (table, creator) == ("medias", 222) else found

        database.rows = loses_a_row

    said = refused(
        tmp_path, spoil, "its medias table holds 2 rows where PostgreSQL holds 3"
    )
    # no value of PostgreSQL's is at fault
    assert exporter.IN_POSTGRESQL not in said


def test_only_a_folder_this_run_made_is_removed_with_its_file(tmp_path):
    database = two_creators(tmp_path)
    of(database, "medias", 222)[1]["media_id"] = "007"
    out = tmp_path / "out"
    # the creator's folder was there, empty
    (out / "222").mkdir(parents=True)

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "1 file couldn't be written:" in said
    assert files(out) == [f"111/{DATABASE}"]
    assert sorted(path.name for path in out.iterdir()) == ["111", "222"]
    assert list((out / "222").iterdir()) == []


def test_rows_that_cant_be_moved_into_the_file_itself_stop_it(tmp_path, monkeypatch):
    # SQLite keeps new rows beside a file (in its -wal file) until it can
    # move them in, which it can't while another program is reading the
    # file. Only the file itself gets the name
    connect = sqlite3.connect
    # not waiting for the reader to finish
    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: connect(*args, **{**kwargs, "timeout": 0}),
    )
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    rows = database.rows
    readers = []

    def someone_reads(site, table, columns, creator):
        if creator == 222 and not readers:
            (being_made,) = (out / "222").glob(f"*{exporter.PARTIAL}")
            reader = connect(being_made)
            readers.append(reader)
            reader.execute("BEGIN")
            reader.execute("SELECT COUNT(*) FROM medias").fetchall()
        return rows(site, table, columns, creator)

    database.rows = someone_reads

    try:
        code, said = run(out, database, apply=True)
    finally:
        for reader in readers:
            reader.close()

    assert code == 1
    assert "onlyfans: 1 file written" in said
    assert "it couldn't be written (the rows couldn't be moved into the file)" in said
    assert f"222/{DATABASE}" not in files(out)


def test_ctrl_c_while_a_files_tables_are_made_leaves_nothing_of_it(
    tmp_path, monkeypatch
):
    # the scraper's code makes the tables on a thread of its own. Ctrl-C
    # stops the run, not that thread, which has the file open until what
    # it was doing is done. Here the thread is given the file to hold, and
    # the run is stopped while it does
    database = two_creators(tmp_path)
    out = tmp_path / "out"
    real = transition.modify_tables
    holding = threading.Event()
    let_go = threading.Event()

    def holds(path):
        with contextlib.closing(sqlite3.connect(path)) as conn:
            conn.execute("SELECT COUNT(*) FROM medias").fetchall()
            holding.set()
            time.sleep(0.5)
        let_go.set()

    async def stopped(db_path, **kwargs):
        if db_path.parent.name != "222":
            return await real(db_path=db_path, **kwargs)
        wrapper._DB_POOL.submit(holds, db_path)
        holding.wait()
        raise KeyboardInterrupt()

    monkeypatch.setattr(transition, "modify_tables", stopped)

    with pytest.raises(KeyboardInterrupt):
        run(out, database, apply=True)

    # the run waited for the thread, and then removed what there was
    assert let_go.is_set()
    assert files(out) == [f"111/{DATABASE}"]
    assert [path.name for path in out.iterdir()] == ["111"]
    assert database.closed == 1


def test_the_files_are_sqlites_own_while_the_scraper_uses_postgresql(
    tmp_path, monkeypatch
):
    # every real run has OFSC_DATABASE_URL set, which sends the scraper's
    # database code to PostgreSQL unless it is told which file to use
    folder = tmp_path / "data"
    current_file(folder / "111" / DATABASE, 111, site="fansly")
    database = holding(folder)
    monkeypatch.setattr(
        postgres, "url", lambda: "postgresql://someone:a-password@db.invalid/library"
    )
    monkeypatch.setattr(postgres, "enabled", lambda: True)
    reached = []

    def refuse(name):
        def inner(*args, **kwargs):
            reached.append(name)
            raise AssertionError(f"PostgreSQL was reached for: {name}")

        return inner

    for name in (
        "where",
        "connect",
        "_pool",
        "check",
        "create_tables",
        "database_exists",
        "table_exists",
        "table_columns",
    ):
        monkeypatch.setattr(postgres.PostgresBackend, name, refuse(name))
    monkeypatch.setattr(wrapper, "_add_backend", refuse("_add_backend"))
    engines = (list(wrapper._BACKENDS), wrapper.DB_ERRORS, wrapper.OPERATIONAL_ERRORS)
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert reached == []
    assert code == 0, said
    assert files(out) == [f"111/{DATABASE}"]
    assert others.get_site_flag(db_path=out / "111" / DATABASE) == "fansly"
    assert sql(out / "111" / DATABASE, "SELECT COUNT(*) FROM medias") == [(3,)]
    # and the scraper's code is left as it was for whatever runs next
    assert (
        list(wrapper._BACKENDS),
        wrapper.DB_ERRORS,
        wrapper.OPERATIONAL_ERRORS,
    ) == engines


def test_tables_from_a_newer_version_are_refused(tmp_path):
    database = two_creators(tmp_path)
    database.had = {"onlyfans": set(ALL_FLAGS) | {"a_later_step"}}
    out = tmp_path / "out"

    code, said = run(out, database, apply=True)

    assert code == 1
    assert "Nothing was written. PostgreSQL's tables for onlyfans were last used" in said
    assert "'a_later_step'" in said
    assert not out.exists()
    assert database.closed == 1


# --- the real database, as far as it goes without a server ---


class Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.found = []

    def __enter__(self):
        return self

    def __exit__(self, *error):
        return False

    def execute(self, query, params=None):
        self.conn.asked.append((" ".join(query.split()), params))
        self.found = self.conn.answer(query)
        return self

    def fetchall(self):
        return self.found


class Connection:
    def __init__(self, answer=lambda query: []):
        self.asked = []
        self.answer = answer

    def cursor(self):
        return Cursor(self)


def real_database(conn):
    database = exporter.Database.__new__(exporter.Database)
    database.conn = conn
    return database


def test_the_server_is_asked_for_one_creators_rows_oldest_first():
    conn = Connection(lambda query: [(1, "a")])
    database = real_database(conn)

    assert database.rows("fansly", "medias", ["media_id", "link"], 111) == [(1, "a")]
    database.rows("onlyfans", "profiles", ["user_id", "username"], 222)

    assert conn.asked == [
        (
            "SELECT media_id, link FROM fansly.medias WHERE model_id = ? ORDER BY id",
            [111],
        ),
        (
            "SELECT user_id, username FROM onlyfans.profiles WHERE user_id = ?"
            " ORDER BY id",
            [222],
        ),
    ]


def test_every_creator_the_tables_name_is_counted():
    def answer(query):
        if "information_schema" in query:
            return [("medias",), ("profiles",), ("schema_flags",), ("notes",)]
        if "schema_flags" in query:
            return [("media_hash",)]
        if "onlyfans.medias" in query:
            return [(111, 3), (222, 1)]
        if "onlyfans.profiles" in query:
            return [(111, 2), (333, 1)]
        raise AssertionError(query)

    conn = Connection(answer)
    database = real_database(conn)

    assert database.held("onlyfans") == {
        111: {"medias": 3, "profiles": 2},
        222: {"medias": 1},
        333: {"profiles": 1},
    }
    assert database.flags("onlyfans") == {"media_hash"}
    assert (
        "SELECT user_id, COUNT(*) FROM onlyfans.profiles GROUP BY user_id",
        None,
    ) in conn.asked
    # tables that were never made hold nothing
    never = real_database(Connection())
    assert never.held("fansly") == {} and never.flags("fansly") == set()


def test_the_database_is_opened_to_read_and_seen_as_at_one_moment():
    conn = Connection()
    opened = []

    def connect(schema, read_only, timeout):
        opened.append((schema, read_only, timeout))
        return conn

    database = real_database(None)
    database.engine = SimpleNamespace(connect=connect)
    database.timeout = 30

    database.open(read_only=False)

    assert opened == [("onlyfans", True, 30)]
    assert conn.asked == [("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ", None)]


# --- the command line ---


def test_the_command_reads_its_own_arguments(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        exporter, "run", lambda folder, **kwargs: calls.append((folder, kwargs)) or 0
    )

    assert exporter.main([str(tmp_path)]) == 0
    assert exporter.main([str(tmp_path), "--apply", "--site", "fansly"]) == 0
    with pytest.raises(SystemExit):
        exporter.main([str(tmp_path), "--site", "elsewhere"])

    assert calls == [
        (tmp_path, dict(apply=False, site=None)),
        (tmp_path, dict(apply=True, site="fansly")),
    ]
