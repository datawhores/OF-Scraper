"""recover_collisions on PostgreSQL (#631): everything that needs no server.

The server is a stand-in (postgres_stand_in.py) that hands rows over as the
real driver does; the tests that use it need the driver installed. It is
SQLite underneath, so it can't show what a server's transaction does: the
`check_...` functions are run again against a real server by
test_collision_recovery_postgres_live.py, in CI, which also has the tests
that only a server can give an answer to.
"""

import ast
import builtins
import json
import os
import re
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
from ofscraper.commands import recover_collisions
from ofscraper.commands.recover_collisions import on_postgres, recover, undo
from ofscraper.db.operations_.media import mediaCreate
from ofscraper.db.operations_.others import schemaCreate, siteInsert
from ofscraper.db.operations_.profile import profilesCreate

URL = "postgresql://scraper:s3cret-word@db.example:5433/library"
# a server nothing listens on
NOWHERE = "postgresql://scraper:s3cret-word@127.0.0.1:9/library"
ROOT = Path(__file__).resolve().parents[1]
CREATOR, NAME = 10, "a_creator"
# a second creator of the same site, and the other site's creator with the
# first one's id
OTHER, OTHER_NAME = 20, "another_creator"
NAMESAKE = "fansly_namesake"
# as large as a Fansly id
BIG = 2**62
COLUMNS = ["media_id", "post_id", "directory", "filename", "downloaded", "size", "hash", "model_id"]
# what `library` holds: rows, media to mark, rows marked, groups
ROWS, TO_MARK, MARKED, GROUPS = 13, 5, 7, 3
# who the name turns out to be, which a report from PostgreSQL says
WHO = {"site": "onlyfans", "model_id": CREATOR, "username": NAME}
MEANWHILE = (
    "Recovery failed: A row was changed by another program while this ran (is the"
    " scraper running?). Nothing was changed. Close the scraper and run this again.\n"
)
# a full path on the other kind of system than the one the tests run on
ELSEWHERE = "/srv/media" if os.name == "nt" else "C:\\media"


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


@pytest.fixture
def server(monkeypatch):
    """A stand-in for the PostgreSQL server, which postgres.Reader reads and
    postgres.Writer changes."""
    pytest.importorskip("psycopg")
    from test.postgres_stand_in import Server

    server = Server()
    monkeypatch.setattr(postgres, "Reader", server.reader)
    monkeypatch.setattr(postgres, "Writer", server.writer)
    yield server
    server.close()


def cli(monkeypatch, capsys, *args, url=URL, ends=True):
    """The command, with the address in its environment for the call only:
    (exit code, stdout, stderr). With `ends`, an interrupt that comes out of
    it as it is fails the test (it would stop the whole test run)."""
    capsys.readouterr()
    with monkeypatch.context() as patch:
        patch.setenv(postgres.URL_KEY, url)
        try:
            code = recover_collisions.main([str(arg) for arg in args]) or 0
        except SystemExit as stopped:
            code = stopped.code
        except KeyboardInterrupt:
            if not ends:
                raise
            pytest.fail("the command was stopped by an interrupt it should have ended on")
    said = capsys.readouterr()
    return code, said.out, said.err


# --- the rows ---


def write_file(db, model_id, username, medias, site=None):
    """A user_data.db with the scraper's own tables and these media rows:
    (media_id, post_id, directory, filename, downloaded, size, hash)."""
    db.parent.mkdir(parents=True)
    with closing(sqlite3.connect(db)) as conn, conn:
        for create in (mediaCreate, profilesCreate, schemaCreate):
            conn.execute(create)
        if site:
            conn.execute(siteInsert, (site,))
        conn.execute("INSERT INTO profiles (user_id, username) VALUES (?, ?)", (model_id, username))
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, directory, filename, downloaded, size, hash, model_id)"
            " VALUES (?,?,?,?,?,?,?,?)",
            [(*row, model_id) for row in medias],
        )
    return db


def library(folder):
    """One creator's media rows, with every kind of row the command tells
    apart. Three groups share a path: an existing file, a missing one, and a
    missing one whose media have an id that isn't a number and a very large
    one."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "shared.jpg").write_bytes(b"the file that survived")
    here = str(folder)
    return [
        (1, 101, here, "shared.jpg", 1, 100, "hash-1"),
        (2, 102, here, "shared.jpg", 1, 200, "hash-2"),
        # the same media in another post: marked with it
        (2, 103, here, "other-post.jpg", 1, 200, "hash-2"),
        (3, 104, here, "alone.jpg", 1, 300, None),
        # not downloaded: counted in its group, with nothing to mark
        (4, 105, here, "missing.jpg", 0, None, None),
        (5, 106, here, "missing.jpg", 1, 500, "hash-5"),
        # one media in two posts is not a collision
        (6, 107, here, "twice.jpg", 1, 1, "hash-6"),
        (6, 108, here, "twice.jpg", 1, 1, "hash-6"),
        ("feedc0de", "c0ffee", here, "avatar.jpg", 1, 7, "hash-7"),
        (BIG, 109, here, "avatar.jpg", 1, 8, ""),
        (7, 110, here, "", 1, 0, None),
        # a row of media 1 without a path: marked with it
        (1, 111, None, None, 1, None, None),
        (8, 112, here, "never.jpg", None, None, None),
    ]


@pytest.fixture
def one_creator(tmp_path):
    """`library` in a creator's file under .data, and an empty folder for the
    undo files."""
    (tmp_path / "undo").mkdir()
    return write_file(
        tmp_path / ".data" / str(CREATOR) / "user_data.db", CREATOR, NAME, library(tmp_path / "media")
    )


@pytest.fixture
def three_creators(one_creator, tmp_path):
    """The same rows, with the same ids and paths, for a second creator of
    the site and for the other site's creator with the first one's id."""
    rows = library(tmp_path / "media")
    write_file(tmp_path / ".data" / str(OTHER) / "user_data.db", OTHER, OTHER_NAME, rows)
    write_file(
        tmp_path / ".data" / "Fansly" / str(CREATOR) / "user_data.db", CREATOR, NAMESAKE, rows, site="fansly"
    )
    return one_creator


@pytest.fixture
def brought_in(one_creator, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    return one_creator


@pytest.fixture
def three_brought_in(three_creators, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    return three_creators


def file_rows(db):
    with closing(creator_rows.FileRows(db)) as rows:
        return [tuple(row) for row in rows.select("medias", COLUMNS)]


def postgres_rows(database_url, creator=CREATOR, site="onlyfans"):
    with creator_rows.in_postgres(database_url, [site]) as found:
        (rows,) = [rows for rows in found if rows.model_id == creator]
        return [tuple(row) for row in rows.select("medias", COLUMNS)]


def held(server):
    """Every row the stand-in holds, as it holds it."""
    return {
        (schema, table): server.db.execute(f"SELECT * FROM {schema}.{table} ORDER BY 1").fetchall()
        for schema in sorted(server.schemas)
        for table in postgres.TABLE_COLUMNS
    }


def without_undo(report):
    """A report without where its undo file is: beside a file, or in a folder."""
    return {**report, "undo_file": report["undo_file"] is not None}


def undo_files(folder):
    return sorted(Path(folder).glob("*.collision-undo-*"))


# --- the same rows, the same recovery ---


def check_same_recovery(database_url, db, undo_dir):
    """A file and the database it was brought into give one report, one set
    of changes and one undo."""
    before = file_rows(db)
    assert postgres_rows(database_url) == before
    name = str(CREATOR)

    from_file = recover(db)
    from_database = on_postgres(database_url, name, undo_dir=undo_dir)
    # the same report, and who the name turned out to be
    assert from_database == {**from_file, "creator": WHO}
    assert list(from_database)[:-1] == list(from_file)
    assert (from_file["media_to_mark"], len(from_file["groups"])) == (TO_MARK, GROUPS)
    assert from_file["groups"][2]["media"] == [
        {"model_id": CREATOR, "media_id": "feedc0de"}, {"model_id": CREATOR, "media_id": BIG},
    ]
    # a preview changes nothing and writes no undo file
    assert postgres_rows(database_url) == file_rows(db) == before
    assert not undo_files(undo_dir) and not undo_files(db.parent)

    from_file = recover(db, apply=True)
    from_database = on_postgres(database_url, name, apply=True, undo_dir=undo_dir)
    assert without_undo(from_database) == {**without_undo(from_file), "creator": WHO}
    assert (from_file["rows_marked"], from_file["applied"]) == (MARKED, True)
    after = file_rows(db)
    assert postgres_rows(database_url) == after
    assert [row[4] for row in after] == [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, None]
    # a full path, in the folder it was told
    assert [Path(from_database["undo_file"])] == undo_files(undo_dir)
    assert Path(from_database["undo_file"]).is_absolute()
    # nothing left to mark, from either
    assert on_postgres(database_url, name, apply=True, undo_dir=undo_dir) == {
        **recover(db, apply=True), "creator": WHO,
    }
    assert len(undo_files(undo_dir)) == 1

    file_undo, database_undo = from_file["undo_file"], from_database["undo_file"]
    previewed = on_postgres(database_url, name, undo_file=database_undo)
    assert undo(db, file_undo) == {"applied": False, "rows_to_restore": MARKED}
    assert previewed == {"applied": False, "rows_to_restore": MARKED, "creator": WHO}
    assert postgres_rows(database_url) == file_rows(db) == after
    restored = on_postgres(database_url, name, undo_file=database_undo, apply=True)
    assert undo(db, file_undo, apply=True) == {"applied": True, "rows_to_restore": MARKED}
    assert restored == {"applied": True, "rows_to_restore": MARKED, "creator": WHO}
    assert postgres_rows(database_url) == file_rows(db) == before
    again = on_postgres(database_url, name, undo_file=database_undo, apply=True)
    assert undo(db, file_undo, apply=True) == {"applied": True, "rows_to_restore": 0}
    assert again == {"applied": True, "rows_to_restore": 0, "creator": WHO}
    assert postgres_rows(database_url) == before


def check_only_that_creator(database_url, snapshot, schema, undo_dir):
    """Of everything the database holds, --apply changes the download flag
    of the one creator's rows in the one site, and the undo sets exactly
    those back. `snapshot` gives every row held: {(schema, table): rows}."""
    before = snapshot()
    flag = postgres.TABLE_COLUMNS["medias"].index("downloaded")
    creator = postgres.TABLE_COLUMNS["medias"].index("model_id")
    # the other creator and the other site hold the same collisions
    assert len(before[schema, "medias"]) == 2 * ROWS

    result = on_postgres(database_url, NAME, site="onlyfans", apply=True, undo_dir=undo_dir)

    assert result["rows_marked"] == MARKED
    after = snapshot()
    assert set(after) == set(before)
    changed = 0
    for key, rows in before.items():
        assert len(after[key]) == len(rows)
        for was, now in zip(rows, after[key]):
            if was == now:
                continue
            assert key == (schema, "medias") and was[creator] == CREATOR
            assert (was[flag], now[flag]) == (1, 0)
            assert was[:flag] + was[flag + 1:] == now[:flag] + now[flag + 1:]
            changed += 1
    assert changed == MARKED

    restored = on_postgres(
        database_url, NAME, site="onlyfans", undo_file=result["undo_file"], apply=True
    )

    assert restored == {"applied": True, "rows_to_restore": MARKED, "creator": WHO}
    assert snapshot() == before


def test_the_same_rows_give_the_same_recovery_from_either(brought_in, tmp_path):
    check_same_recovery(URL, brought_in, tmp_path / "undo")


def test_only_that_creators_rows_of_that_site_are_touched(three_brought_in, server, tmp_path):
    check_only_that_creator(URL, lambda: held(server), "onlyfans", tmp_path / "undo")


# --- preview and apply ---


@pytest.mark.parametrize("folder", [[], ["--undo-dir", "undo"]])
def test_a_preview_only_reads(brought_in, server, tmp_path, monkeypatch, capsys, folder):
    monkeypatch.chdir(tmp_path)
    before = held(server)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, *folder)

    assert (code, err) == (0, "")
    report = json.loads(out)
    assert (report["applied"], report["media_to_mark"], report["rows_marked"]) == (False, TO_MARK, 0)
    assert report["undo_file"] is None
    # nothing is left in the folder it would write to, or the one it is run in
    assert list((tmp_path / "undo").iterdir()) == [] and not undo_files(tmp_path)
    assert held(server) == before
    # one connection, to the address in the environment, that can't change rows
    assert [event for event in server.events if event[0] == "connect"] == [("connect", URL)]
    assert {event[0] for event in server.events} == {"connect", "query", "close"}
    assert all(event[1].startswith("SELECT ") for event in server.events if event[0] == "query")
    assert server.events[-1] == ("close",)


def test_apply_saves_the_undo_file_first_then_changes_everything_in_one_transaction(
    brought_in, server, tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    before = held(server)
    seen = {}
    synced = os.fsync

    def fsync(descriptor):
        # the undo file, written out in full by the time it is made to stay
        (saved,) = undo_files(tmp_path / "undo")
        server.events.append(("fsync", len(json.loads(saved.read_text(encoding="utf-8"))["rows"])))
        return synced(descriptor)

    def before_the_first_change():
        (saved,) = undo_files(tmp_path / "undo")
        seen["rows"] = len(json.loads(saved.read_text(encoding="utf-8"))["rows"])
        seen["held"] = held(server)

    monkeypatch.setattr(os, "fsync", fsync)
    server.before_change = before_the_first_change

    # the folder as it is typed, from where the command is run
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", "undo")

    assert (code, err) == (0, "")
    report = json.loads(out)
    assert (report["applied"], report["rows_marked"]) == (True, MARKED)
    # the whole undo file was there before anything was changed
    assert seen == {"rows": MARKED, "held": before}
    # and was made to stay on the disk before that, not after
    kinds = [event[0] for event in server.events]
    assert ("fsync", MARKED) in server.events and kinds.count("fsync") == 1
    assert kinds.index("fsync") < kinds.index("change")
    # the report gives its full path
    (saved,) = undo_files(tmp_path / "undo")
    assert report["undo_file"] == str(saved) and saved.is_absolute()
    assert not undo_files(tmp_path)
    assert re.fullmatch(r"postgresql-onlyfans-10\.collision-undo-[0-9a-f]{32}\.json", saved.name)
    kinds = [event[0] for event in server.events]
    assert kinds.count("connect") == 1 and kinds.count("open for changes") == 1
    assert kinds.count("change") == MARKED and kinds.count("commit") == 1
    # every change, then the one commit, then the connection is closed
    assert kinds[-MARKED - 2:] == ["change"] * MARKED + ["commit", "close"]
    assert held(server) != before


def test_the_undo_file_goes_to_the_folder_it_is_told(brought_in, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    code, out, _ = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert code == 0
    assert [Path(json.loads(out)["undo_file"])] == undo_files(tmp_path / "undo")
    assert not undo_files(tmp_path)


def test_the_undo_file_names_each_row_by_its_media_and_post_and_says_what_it_held(brought_in, tmp_path):
    here = str(tmp_path / "media")

    result = on_postgres(URL, NAME, apply=True, undo_dir=tmp_path / "undo")

    text = Path(result["undo_file"]).read_text(encoding="utf-8")
    assert json.loads(text) == {
        "version": 2,
        "source": "postgresql",
        "site": "onlyfans",
        "model_id": CREATOR,
        "database": "db.example:5433/library",
        "rows": [
            {"media_id": media_id, "post_id": post_id, "downloaded": 1, "directory": directory,
             "filename": filename, "size": size, "hash": digest}
            for media_id, post_id, directory, filename, size, digest in [
                (1, 101, here, "shared.jpg", 100, "hash-1"),
                (2, 102, here, "shared.jpg", 200, "hash-2"),
                (2, 103, here, "other-post.jpg", 200, "hash-2"),
                (5, 106, here, "missing.jpg", 500, "hash-5"),
                ("feedc0de", "c0ffee", here, "avatar.jpg", 7, "hash-7"),
                (BIG, 109, here, "avatar.jpg", 8, ""),
                (1, 111, None, None, None, None),
            ]
        ],
    }
    # where it was made, without the login
    assert "s3cret-word" not in text and "scraper" not in text


def test_an_address_that_names_no_server_leaves_that_out_of_the_undo_file(brought_in, tmp_path):
    result = on_postgres("host=db.example dbname=library password=s3cret-word", NAME, apply=True, undo_dir=tmp_path / "undo")

    text = Path(result["undo_file"]).read_text(encoding="utf-8")
    assert list(json.loads(text)) == ["version", "source", "site", "model_id", "rows"]
    assert "s3cret-word" not in text and "db.example" not in text


def test_an_undo_file_that_is_there_already_is_never_replaced(brought_in, server, tmp_path, monkeypatch, capsys):
    """Two runs can't be given one name, but if they were: the file that is
    there is another run's way back."""
    before = held(server)
    monkeypatch.setattr(recover_collisions.uuid, "uuid4", lambda: SimpleNamespace(hex="0" * 32))
    taken = tmp_path / "undo" / ("postgresql-onlyfans-10.collision-undo-" + "0" * 32 + ".json")
    taken.write_text("another run's undo file", encoding="utf-8")

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out) == (1, "")
    assert err.startswith("Recovery failed: ") and taken.name in err and err.count("\n") == 1
    # it is neither written over nor removed, and nothing is changed
    assert taken.read_text(encoding="utf-8") == "another run's undo file"
    assert undo_files(tmp_path / "undo") == [taken]
    assert held(server) == before
    assert not [event for event in server.events if event[0] in ("change", "commit")]


def test_if_the_undo_file_cant_be_saved_nothing_is_changed(brought_in, server, tmp_path, monkeypatch, capsys):
    before = held(server)
    original = Path.open

    def deny_undo(path, *args, **kwargs):
        if ".collision-undo-" in path.name:
            raise PermissionError("undo file denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_undo)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out, err) == (1, "", "Recovery failed: undo file denied\n")
    assert held(server) == before
    assert not [event for event in server.events if event[0] in ("change", "commit")]
    assert server.events[-1] == ("close",)


@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_an_undo_folder_that_cant_take_a_file_is_said_before_anything_is_done(
    brought_in, server, tmp_path, monkeypatch, capsys, apply
):
    """A preview finds it out, so that the apply after it doesn't."""
    server.events.clear()
    (tmp_path / "a-file").write_text("", encoding="utf-8")

    for folder in ("no-such-folder", "a-file"):
        code, out, err = cli(
            monkeypatch, capsys, "--postgres", "--creator", NAME, *apply, "--undo-dir", tmp_path / folder
        )

        assert (code, out) == (1, "")
        assert err == f"Recovery failed: The undo folder {tmp_path / folder} isn't there, or isn't a folder\n"
    assert not (tmp_path / "no-such-folder").exists()

    def denied(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(recover_collisions.tempfile, "TemporaryFile", denied)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, *apply, "--undo-dir", tmp_path / "undo"
    )

    assert (code, out) == (1, "")
    assert err == f"Recovery failed: The undo folder {tmp_path / 'undo'} can't be written to (Permission denied)\n"
    # the database wasn't asked anything
    assert server.events == []


def test_apply_needs_a_folder_for_the_undo_file(brought_in, server, tmp_path, monkeypatch, capsys):
    """The folder the command is run in may not be kept (in Docker it is
    inside the container), and the undo file is the only way back."""
    monkeypatch.chdir(tmp_path / "undo")
    server.events.clear()

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply")

    assert (code, out) == (2, "")
    assert err.endswith(
        "error: --postgres --apply needs --undo-dir: the folder for the undo file, which is the only way"
        " back. Give a folder that is kept (in Docker a mounted one, not one inside the container)\n"
    )
    assert server.events == [] and not undo_files(tmp_path / "undo")
    # the same without the command line
    with pytest.raises(ValueError, match="A folder for the undo file is needed to apply"):
        on_postgres(URL, NAME, apply=True)
    assert server.events == []


def fail_after(monkeypatch, made, outcome):
    """PostgresRows.change, failing once `made` changes went through:
    `outcome` is raised, or returned if it isn't an error."""
    real = creator_rows.PostgresRows.change
    calls = []

    def change(self, *args):
        calls.append(args)
        if len(calls) > made:
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return real(self, *args)

    monkeypatch.setattr(creator_rows.PostgresRows, "change", change)
    return calls


@pytest.mark.parametrize(
    "outcome, said",
    [
        (
            postgres.PostgresUnavailable("Can't change the PostgreSQL database at db.example:5433/library."),
            "Recovery failed: Can't change the PostgreSQL database at db.example:5433/library.\n",
        ),
        # the row no longer holds what was read from it
        (False, MEANWHILE),
    ],
)
def test_a_change_that_fails_part_way_leaves_every_row_as_it_was(
    brought_in, server, tmp_path, monkeypatch, capsys, outcome, said
):
    before = held(server)
    calls = fail_after(monkeypatch, 3, outcome)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out, err) == (1, "", said)
    assert len(calls) == 4
    # the three that were made are gone, and so is the undo file
    assert held(server) == before
    assert not undo_files(tmp_path / "undo")
    assert "commit" not in [event[0] for event in server.events]


def test_stopped_between_two_changes_no_row_is_changed_and_no_undo_file_is_left(
    brought_in, server, tmp_path, monkeypatch, capsys
):
    """Ctrl-C before the changes are saved: as if the command hadn't run."""
    before = held(server)
    calls = fail_after(monkeypatch, 3, KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        cli(
            monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo",
            ends=False,
        )

    assert len(calls) == 4
    assert held(server) == before
    assert not undo_files(tmp_path / "undo")
    kinds = [event[0] for event in server.events]
    assert "commit" not in kinds and kinds[-1] == "close"


def cant_remove(monkeypatch):
    """The undo file can't be removed (the folder was made read-only
    meanwhile, or another program holds the file)."""
    real = Path.unlink

    def unlink(path, *args, **kwargs):
        if ".collision-undo-" in path.name:
            raise PermissionError(13, "Permission denied")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)


@pytest.mark.parametrize(
    "outcome, reason",
    [
        (
            False,
            "A row was changed by another program while this ran (is the scraper running?). Nothing was changed."
            " Close the scraper and run this again.",
        ),
        (
            postgres.PostgresUnavailable("Can't change the PostgreSQL database at db.example:5433/library. (no)"),
            "Can't change the PostgreSQL database at db.example:5433/library. (no). Nothing was changed.",
        ),
    ],
)
def test_an_undo_file_that_cant_be_removed_doesnt_hide_what_went_wrong(
    brought_in, server, tmp_path, monkeypatch, capsys, outcome, reason
):
    before = held(server)
    fail_after(monkeypatch, 3, outcome)
    cant_remove(monkeypatch)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    (left,) = undo_files(tmp_path / "undo")
    assert (code, out) == (1, "")
    assert err == (
        f"Recovery failed: {reason} The undo file {left} could not be removed (Permission denied):"
        " nothing needs it, and it is safe to delete.\n"
    )
    assert held(server) == before
    assert "commit" not in [event[0] for event in server.events]


def test_stopped_with_an_undo_file_that_cant_be_removed_it_still_stops(
    brought_in, server, tmp_path, monkeypatch, capsys
):
    before = held(server)
    fail_after(monkeypatch, 3, KeyboardInterrupt())
    cant_remove(monkeypatch)

    with pytest.raises(KeyboardInterrupt):
        cli(
            monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo",
            ends=False,
        )

    assert held(server) == before


def test_a_row_the_scraper_changed_meanwhile_is_not_overwritten(brought_in, server, tmp_path, monkeypatch, capsys):
    before = postgres_rows(URL)
    # between the command's read and its changes, a download is saved
    server.before_change = lambda: server.elsewhere(
        "UPDATE onlyfans.medias SET filename = 'missing_5.jpg', size = 501, hash = 'new' WHERE post_id = '106'"
    )

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out, err) == (1, "", MEANWHILE)
    after = postgres_rows(URL)
    # the scraper's row is as the scraper left it, still downloaded
    assert after[5] == (5, 106, str(tmp_path / "media"), "missing_5.jpg", 1, 501, "new", CREATOR)
    assert after[:5] + after[6:] == before[:5] + before[6:]
    assert not undo_files(tmp_path / "undo")


def test_a_change_the_server_refuses_because_of_the_scraper_changes_nothing(
    brought_in, server, tmp_path, monkeypatch, capsys
):
    """What a server does when a row was changed after the command's first
    read (see the live tests): the stand-in is told to."""
    before = held(server)
    server.change_error = postgres.ChangedMeanwhile(
        "Another program changed or is using the same rows of the PostgreSQL database at"
        " db.example:5433/library (is the scraper running?). Nothing was changed."
        " (could not serialize access due to concurrent update)"
    )

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out) == (1, "")
    assert err == f"Recovery failed: {server.change_error}\n"
    assert held(server) == before
    assert not undo_files(tmp_path / "undo")


# --- once the changes are being saved ---
# Only the server knows whether it kept them, so the undo file stays whatever
# stops the command, and the command says so.

LOST = (
    "The connection to the PostgreSQL database at db.example:5433/library was lost while the changes"
    " were being saved, so it isn't known whether they were. (server closed the connection unexpectedly)"
)
STOPPED = (
    "This was stopped while the changes were being saved to the PostgreSQL database at"
    " db.example:5433/library, so it isn't known whether they were."
)
KEPT = "The undo file is kept: {}. Run this with --undo and that file, without --apply, to see whether the changes arrived."


def lost():
    import psycopg

    return psycopg.OperationalError("server closed the connection\n\tunexpectedly")


@pytest.mark.parametrize(
    "stopped_by, arrived, code, said",
    [
        # the connection went
        (lost, False, 1, LOST),
        (lost, True, 1, LOST),
        # Ctrl-C, which the driver passes on whatever became of the commit
        (KeyboardInterrupt, False, 130, STOPPED),
        (KeyboardInterrupt, True, 130, STOPPED),
        # the program was told to end
        (SystemExit, True, 1, STOPPED),
    ],
)
def test_whatever_stops_the_saving_the_undo_file_is_kept_and_it_is_said(
    brought_in, server, tmp_path, monkeypatch, capsys, stopped_by, arrived, code, said
):
    before = held(server)
    setattr(server, "commit_answer_lost" if arrived else "commit_error", stopped_by())

    exit_code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    (saved,) = undo_files(tmp_path / "undo")
    assert (exit_code, out) == (code, "")
    # one sentence, with the file where it says it is
    assert err == f"Recovery failed: {said} {KEPT.format(saved)}\n"
    assert len(json.loads(saved.read_text(encoding="utf-8"))["rows"]) == MARKED
    assert (held(server) != before) == arrived

    # the undo file tells which it was, and is the way back if they arrived
    server.commit_error = server.commit_answer_lost = None
    exit_code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", saved)
    assert (exit_code, err) == (0, "")
    assert json.loads(out)["rows_to_restore"] == (MARKED if arrived else 0)
    exit_code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", saved, "--apply")
    assert (exit_code, err) == (0, "")
    assert held(server) == before


@pytest.mark.parametrize("stopped_by, code", [(KeyboardInterrupt, 130), (SystemExit, 1), (RuntimeError, 1)])
def test_the_undo_file_is_kept_whoever_the_commit_is_stopped_in(
    brought_in, server, tmp_path, monkeypatch, capsys, stopped_by, code
):
    """Not only what the connection's commit makes of it: anything that comes
    out of the rows' commit, once it was called."""

    def commit(self):
        raise stopped_by()

    monkeypatch.setattr(creator_rows.PostgresRows, "commit", commit)

    exit_code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    (saved,) = undo_files(tmp_path / "undo")
    assert (exit_code, out) == (code, "")
    assert err == (
        "Recovery failed: This was stopped while the changes were being saved to PostgreSQL, so it isn't"
        f" known whether they were. {KEPT.format(saved)}\n"
    )


def test_an_undo_is_said_to_be_unconfirmed_whoever_its_commit_is_stopped_in(recovered, server, monkeypatch, capsys):
    _, undo_file, _, _ = recovered

    def commit(self):
        raise KeyboardInterrupt

    monkeypatch.setattr(creator_rows.PostgresRows, "commit", commit)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply")

    assert (code, out) == (130, "")
    assert err == (
        "Recovery failed: This was stopped while the changes were being saved to PostgreSQL, so it isn't"
        " known whether they were. Run the same --undo again, without --apply: it shows what is left to"
        " restore.\n"
    )


@pytest.mark.parametrize("stopped_by, arrived, code", [(lost, False, 1), (KeyboardInterrupt, True, 130)])
def test_an_undo_that_is_stopped_while_it_is_saved_says_how_to_see_what_is_left(
    recovered, server, monkeypatch, capsys, stopped_by, arrived, code
):
    _, undo_file, before, marked = recovered
    setattr(server, "commit_answer_lost" if arrived else "commit_error", stopped_by())

    exit_code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply")

    assert (exit_code, out) == (code, "")
    assert err == (
        f"Recovery failed: {STOPPED if arrived else LOST} Run the same --undo again, without --apply:"
        " it shows what is left to restore.\n"
    )
    assert held(server) == (before if arrived else marked)
    assert Path(undo_file).exists()
    assert "Traceback" not in err and err.count("\n") == 1

    server.commit_error = server.commit_answer_lost = None
    exit_code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file)
    assert (exit_code, err) == (0, "")
    assert json.loads(out)["rows_to_restore"] == (0 if arrived else MARKED)


# --- undo ---


@pytest.fixture
def recovered(brought_in, server, tmp_path):
    """The library after --apply: (the file, the undo file, every row held
    before, every row held now)."""
    before = held(server)
    result = on_postgres(URL, NAME, apply=True, undo_dir=tmp_path / "undo")
    server.events.clear()
    return brought_in, result["undo_file"], before, held(server)


def test_cli_undo_previews_then_restores_exactly(recovered, server, monkeypatch, capsys):
    _, undo_file, before, marked = recovered

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file)

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": False, "rows_to_restore": MARKED, "creator": WHO}
    assert held(server) == marked
    assert {event[0] for event in server.events} == {"connect", "query", "close"}

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", str(CREATOR), "--undo", undo_file, "--apply")

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": True, "rows_to_restore": MARKED, "creator": WHO}
    assert held(server) == before
    assert [event[0] for event in server.events][-MARKED - 2:] == ["change"] * MARKED + ["commit", "close"]


@pytest.fixture
def three_recovered(three_brought_in, server, tmp_path):
    before = held(server)
    result = on_postgres(URL, NAME, apply=True, undo_dir=tmp_path / "undo")
    return three_brought_in, result["undo_file"], before, held(server)


@pytest.mark.parametrize(
    "args, said",
    [
        (["--creator", OTHER_NAME], "Undo file is for onlyfans creator 10, not onlyfans creator 20"),
        (["--creator", "10", "--site", "fansly"], "Undo file is for onlyfans creator 10, not fansly creator 10"),
        (["--creator", NAMESAKE], "Undo file is for onlyfans creator 10, not fansly creator 10"),
    ],
)
@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_undo_is_refused_for_another_creator_or_site(three_recovered, server, monkeypatch, capsys, args, said, apply):
    """The other creator and the other site hold rows the undo file would
    fit: the same media, posts, paths and sizes."""
    _, undo_file, _, marked = three_recovered

    code, out, err = cli(monkeypatch, capsys, "--postgres", *args, "--undo", undo_file, *apply)

    assert (code, out, err) == (1, "", f"Recovery failed: {said}\n")
    assert held(server) == marked


@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_an_undo_file_from_a_file_is_refused_for_postgresql_and_the_reverse(
    recovered, server, monkeypatch, capsys, apply
):
    db, database_undo, _, marked = recovered
    file_undo = recover(db, apply=True)["undo_file"]
    in_file = file_rows(db)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", file_undo, *apply)

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: Undo file was written for a user_data.db, not PostgreSQL:"
        " give that file in place of --postgres\n"
    )
    assert held(server) == marked

    with pytest.raises(SystemExit) as stopped:
        recover_collisions.main([str(db), "--undo", database_undo, *apply])

    said = capsys.readouterr()
    assert (stopped.value.code, said.out) == (1, "")
    assert said.err == (
        "Recovery failed: Undo file was written from PostgreSQL, not a user_data.db:"
        " give --postgres and --creator in place of the database\n"
    )
    assert file_rows(db) == in_file


@pytest.mark.parametrize(
    "since",
    [
        # downloaded again, under a name of its own
        "UPDATE onlyfans.medias SET downloaded = 1, filename = 'missing_5.jpg' WHERE post_id = '106'",
        # another file by now, though not downloaded
        "UPDATE onlyfans.medias SET size = 501 WHERE post_id = '106'",
        "UPDATE onlyfans.medias SET hash = NULL WHERE post_id = '106'",
        "UPDATE onlyfans.medias SET directory = NULL WHERE post_id = '106'",
        # set back to never tried
        "UPDATE onlyfans.medias SET downloaded = NULL WHERE post_id = '106'",
        "DELETE FROM onlyfans.medias WHERE post_id = '106'",
    ],
)
@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_undo_is_refused_when_a_row_changed_since(recovered, server, monkeypatch, capsys, since, apply):
    _, undo_file, _, _ = recovered
    server.elsewhere(since)
    changed = held(server)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, *apply)

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: 1 of the undo file's 7 rows are no longer as the recovery left them"
        " (media downloaded again since, or another database). Nothing was restored\n"
    )
    assert held(server) == changed
    assert "change" not in [event[0] for event in server.events]


ANOTHER = "postgresql://scraper:s3cret-word@other.example:5432/a_copy"


@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_an_undo_that_doesnt_fit_says_where_the_undo_file_was_made_if_not_here(
    recovered, server, monkeypatch, capsys, apply
):
    """A hint: the rows are what is checked, since a database's address can
    change."""
    _, undo_file, before, marked = recovered

    # the rows fit: the address is not asked about
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, url=ANOTHER)
    assert (code, err) == (0, "")
    assert json.loads(out)["rows_to_restore"] == MARKED

    server.elsewhere("UPDATE onlyfans.medias SET size = 501 WHERE post_id = '106'")
    changed = held(server)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, *apply, url=ANOTHER
    )

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: 1 of the undo file's 7 rows are no longer as the recovery left them"
        " (media downloaded again since, or another database: the undo file was made on"
        " db.example:5433/library, this is other.example:5432/a_copy). Nothing was restored\n"
    )
    assert held(server) == changed


def without_where_it_was_made(undo_file):
    """The undo file as it would be without that line."""
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    del record["database"]
    Path(undo_file).write_text(json.dumps(record), encoding="utf-8")


def test_an_undo_file_that_doesnt_say_where_it_was_made_still_works(recovered, server, monkeypatch, capsys):
    _, undo_file, before, _ = recovered
    without_where_it_was_made(undo_file)
    server.elsewhere("UPDATE onlyfans.medias SET size = 501 WHERE post_id = '106'")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, url=ANOTHER)

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: 1 of the undo file's 7 rows are no longer as the recovery left them"
        " (media downloaded again since, or another database). Nothing was restored\n"
    )

    server.elsewhere("UPDATE onlyfans.medias SET size = 500 WHERE post_id = '106'")

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply", url=ANOTHER
    )

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": True, "rows_to_restore": MARKED, "creator": WHO}
    assert held(server) == before


@pytest.mark.parametrize("again", [lambda row: dict(row), lambda row: {**row, "media_id": "1", "post_id": "101"}])
@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_an_undo_file_that_lists_a_row_twice_is_refused(recovered, server, monkeypatch, capsys, again, apply):
    """Not one this command wrote: the second time, in figures or in quotes."""
    _, undo_file, _, marked = recovered
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    assert (record["rows"][0]["media_id"], record["rows"][0]["post_id"]) == (1, 101)
    record["rows"].append(again(record["rows"][0]))
    Path(undo_file).write_text(json.dumps(record), encoding="utf-8")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, *apply)

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: Undo file lists a row twice (media 1, post 101): it isn't one this command"
        " wrote. Nothing was restored\n"
    )
    assert held(server) == marked
    assert not [event for event in server.events if event[0] in ("change", "commit")]


def test_an_undo_file_with_its_ids_in_quotes_is_the_same_undo_file(recovered, server, monkeypatch, capsys):
    """Written out again by another program, the ids may come as text: they
    name the same creator and the same rows."""
    _, undo_file, before, _ = recovered
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    record["model_id"] = str(record["model_id"])
    for row in record["rows"]:
        row["media_id"], row["post_id"] = str(row["media_id"]), str(row["post_id"])
    Path(undo_file).write_text(json.dumps(record), encoding="utf-8")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply")

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": True, "rows_to_restore": MARKED, "creator": WHO}
    assert held(server) == before


def test_undo_leaves_a_row_that_is_downloaded_again_with_the_file_it_had(recovered, server, monkeypatch, capsys):
    """It is as the undo would leave it: there is nothing to restore in it."""
    _, undo_file, before, _ = recovered
    server.elsewhere("UPDATE onlyfans.medias SET downloaded = 1 WHERE post_id = '106'")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply")

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": True, "rows_to_restore": MARKED - 1, "creator": WHO}
    assert held(server) == before


@pytest.mark.parametrize(
    "saved, flags",
    [
        # downloaded again, under a name of its own
        ("downloaded = 1, filename = 'avatar_2.jpg'", [0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0, None]),
        # another file by now, though not downloaded
        ("size = 9", [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, None]),
    ],
)
def test_undo_restores_nothing_if_a_row_changes_while_it_runs(recovered, server, monkeypatch, capsys, saved, flags):
    _, undo_file, _, marked = recovered
    server.before_change = lambda: server.elsewhere(f"UPDATE onlyfans.medias SET {saved} WHERE post_id = '109'")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply")

    assert (code, out, err) == (1, "", MEANWHILE)
    now, was = held(server)["onlyfans", "medias"], marked["onlyfans", "medias"]
    flag = postgres.TABLE_COLUMNS["medias"].index("downloaded")
    # only the scraper's change was kept: the rows restored before it are back
    assert [row[flag] for row in now] == flags
    assert now[9] != was[9] and now[:9] + now[10:] == was[:9] + was[10:]
    assert "commit" not in [event[0] for event in server.events]


ROW = {"media_id": 1, "post_id": 101, "downloaded": 1, "directory": "d", "filename": "f", "size": 1, "hash": "h"}


@pytest.mark.parametrize(
    "content, said",
    [
        ("not json", "Expecting value"),
        ("[]", "Invalid undo file"),
        ('{"version": 3, "source": "postgresql"}', "Undo file was written by a version of this command that this one doesn't know"),
        (json.dumps({"version": 2, "source": "postgresql", "site": "onlyfans", "model_id": 10}), "Invalid undo rows"),
        (json.dumps({"version": 2, "source": "postgresql", "site": "onlyfans", "model_id": 10, "rows": [[1, 2, 1]]}),
         "Invalid undo rows"),
        (json.dumps({"version": 2, "source": "postgresql", "site": "onlyfans", "model_id": 10,
                     "rows": [{**ROW, "downloaded": 0}]}), "Invalid undo rows"),
        (json.dumps({"version": 2, "source": "postgresql", "site": "onlyfans", "model_id": 10,
                     "rows": [{key: value for key, value in ROW.items() if key != "hash"}]}), "Invalid undo rows"),
        (json.dumps({"version": 2, "source": "postgresql", "site": "onlyfans", "model_id": 10,
                     "rows": [{**ROW, "media_id": None}]}), "Invalid undo rows"),
        (json.dumps({"version": 2, "source": "postgresql", "site": "onlyfans", "model_id": 10,
                     "rows": [{**ROW, "id": 4}]}), "Invalid undo rows"),
    ],
)
def test_an_undo_file_that_cant_be_read_is_said(recovered, server, tmp_path, monkeypatch, capsys, content, said):
    _, _, _, marked = recovered
    undo_file = tmp_path / "written-by-hand.json"
    undo_file.write_text(content, encoding="utf-8")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, "--undo", undo_file, "--apply")

    assert (code, out) == (1, "")
    assert err.startswith(f"Recovery failed: {said}") and err.count("\n") == 1
    assert held(server) == marked


# --- which creator ---


def test_the_creator_is_named_by_username_or_id(three_brought_in, monkeypatch, capsys):
    def marked(*args):
        code, out, err = cli(monkeypatch, capsys, "--postgres", *args)
        assert (code, err) == (0, "")
        report = json.loads(out)
        # the creator in the groups is the creator the report names
        assert {media["model_id"] for group in report["groups"] for media in group["media"]} == {
            report["creator"]["model_id"]
        }
        return report["media_to_mark"], report["creator"]

    first = {"site": "onlyfans", "model_id": CREATOR, "username": NAME}
    second = {"site": "onlyfans", "model_id": OTHER, "username": OTHER_NAME}
    namesake = {"site": "fansly", "model_id": CREATOR, "username": NAMESAKE}
    assert marked("--creator", NAME) == (TO_MARK, first)
    assert marked("--creator", "A_Creator") == (TO_MARK, first)
    assert marked("--creator", OTHER_NAME) == (TO_MARK, second)
    assert marked("--creator", str(OTHER)) == (TO_MARK, second)
    assert marked("--creator", NAMESAKE) == (TO_MARK, namesake)
    # an id both sites have needs its site
    assert marked("--creator", str(CREATOR), "--site", "onlyfans") == (TO_MARK, first)
    assert marked("--creator", str(CREATOR), "--site", "fansly") == (TO_MARK, namesake)


def test_the_report_says_who_the_name_turned_out_to_be(three_brought_in, server, tmp_path, monkeypatch, capsys):
    """A number that is one creator's username and nobody's id works on that
    creator: without the report saying so, an empty report reads as "that
    creator has no collisions"."""
    # saved with capitals, then under a name that is all figures
    server.insert("onlyfans", "profiles", ["user_id", "username"], [(999, "Capital_Letters"), (999, "12345")])
    server.insert("onlyfans", "medias", ["media_id", "post_id", "downloaded", "model_id"], [("1", "1", True, 999)])
    # only ever saved with capitals, and with no profile at all
    server.insert("onlyfans", "profiles", ["user_id", "username"], [(998, "Only_Capitals")])
    server.insert("onlyfans", "medias", ["media_id", "post_id", "downloaded", "model_id"], [("1", "1", True, 998)])
    server.insert("onlyfans", "medias", ["media_id", "post_id", "downloaded", "model_id"], [("1", "1", True, 997)])
    nothing = {"groups": [], "media_to_mark": 0, "rows_marked": 0, "undo_file": None, "applied": False}

    for typed, creator in [
        ("12345", {"site": "onlyfans", "model_id": 999, "username": "12345"}),
        ("capital_letters", {"site": "onlyfans", "model_id": 999, "username": "12345"}),
        ("CAPITAL_LETTERS", {"site": "onlyfans", "model_id": 999, "username": "12345"}),
        ("999", {"site": "onlyfans", "model_id": 999, "username": "12345"}),
        # the username as it is saved, however it was typed
        ("only_capitals", {"site": "onlyfans", "model_id": 998, "username": "Only_Capitals"}),
        ("Only_Capitals", {"site": "onlyfans", "model_id": 998, "username": "Only_Capitals"}),
        ("997", {"site": "onlyfans", "model_id": 997, "username": None}),
    ]:
        for apply in ([], ["--apply", "--undo-dir", tmp_path / "undo"]):
            code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", typed, *apply)

            assert (code, err) == (0, "")
            assert json.loads(out) == {**nothing, "applied": bool(apply), "creator": creator}


@pytest.mark.parametrize("apply", [[], ["--apply"]])
def test_a_name_that_fits_two_creators_is_refused(three_brought_in, server, tmp_path, monkeypatch, capsys, apply):
    before = held(server)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", CREATOR, *apply, "--undo-dir", tmp_path / "undo"
    )

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: PostgreSQL has more than one creator named 10: onlyfans 10 (a_creator),"
        " fansly 10 (fansly_namesake). Give --site, or a username or id that only one of them has\n"
    )
    assert held(server) == before
    assert not undo_files(tmp_path / "undo")
    assert server.events[-1] == ("close",)


def check_one_creator_or_none(database_url, add, undo_dir):
    """A name that more than one creator goes by changes nothing, whatever
    else is given with it, and each of them can still be named. `add` puts
    rows in a table of the first site: (table, columns, rows)."""
    # a creator whose username is another creator's id, with a username the
    # other creator had before
    add("profiles", ["user_id", "username"], [(77, str(OTHER)), (77, "second_name"), (OTHER, "second_name")])
    add("medias", ["media_id", "post_id", "downloaded", "model_id"], [("1", "1", True, 77)])
    before = {creator: postgres_rows(database_url, creator) for creator in (CREATOR, OTHER, 77)}

    def run(name, site=None, apply=True):
        return on_postgres(database_url, name, site=site, apply=apply, undo_dir=undo_dir)

    both = f"onlyfans {OTHER} ({OTHER_NAME}, second_name), onlyfans 77 ({OTHER}, second_name)"
    choose = "Give --site, or a username or id that only one of them has"
    for name, site, fits in [
        (str(OTHER), None, both),
        (str(OTHER), "onlyfans", both),
        ("Second_Name", None, both),
        ("second_name", "onlyfans", both),
        (str(CREATOR), None, f"onlyfans {CREATOR} ({NAME}), fansly {CREATOR} ({NAMESAKE})"),
    ]:
        for apply in (False, True):
            with pytest.raises(ValueError) as refused:
                run(name, site, apply)
            assert str(refused.value) == f"PostgreSQL has more than one creator named {name}: {fits}. {choose}"
    assert {creator: postgres_rows(database_url, creator) for creator in before} == before
    assert not undo_files(undo_dir)

    # each can be named by what only it has, and the report says who it is,
    # with the username that was saved last
    named = run(OTHER_NAME, apply=False)
    assert named["groups"][0]["media"][0]["model_id"] == OTHER
    assert named["creator"] == {"site": "onlyfans", "model_id": OTHER, "username": "second_name"}
    assert run("77", apply=False) == {
        "groups": [], "media_to_mark": 0, "rows_marked": 0, "undo_file": None, "applied": False,
        "creator": {"site": "onlyfans", "model_id": 77, "username": "second_name"},
    }
    assert run(str(CREATOR), "fansly")["rows_marked"] == MARKED
    assert postgres_rows(database_url, OTHER) == before[OTHER]
    assert postgres_rows(database_url, 77) == before[77]
    assert postgres_rows(database_url) == before[CREATOR]


def test_a_name_more_than_one_creator_goes_by_is_refused_and_each_can_still_be_named(
    three_brought_in, server, tmp_path
):
    check_one_creator_or_none(URL, lambda *rows: server.insert("onlyfans", *rows), tmp_path / "undo")


def test_a_creator_nobody_has_is_said(three_brought_in, server, tmp_path, monkeypatch, capsys):
    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", "Nobody_Here", "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out) == (1, "")
    # the name as it was typed
    assert err == "Recovery failed: PostgreSQL has no creator named Nobody_Here (looked in: onlyfans, fansly)\n"

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", OTHER_NAME, "--site", "fansly")

    assert (code, out) == (1, "")
    assert err == f"Recovery failed: PostgreSQL has no creator named {OTHER_NAME} (looked in: fansly)\n"
    assert server.events[-1] == ("close",)


# --- the recorded paths ---


def two_media(server, directory):
    server.insert(
        "onlyfans", "medias",
        ["media_id", "post_id", "directory", "filename", "downloaded", "model_id"],
        [(1, 1, directory, "a.jpg", True, CREATOR), (2, 2, directory, "a.jpg", True, CREATOR)],
    )


def test_relative_recorded_paths_need_the_folder_they_start_from(server, tmp_path, monkeypatch, capsys):
    two_media(server, "downloads")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", CREATOR, "--apply", "--undo-dir", tmp_path)

    assert (code, out) == (1, "")
    assert err == "Recovery failed: Relative recorded paths require --path-root (the original working directory)\n"
    assert [row[4] for row in postgres_rows(URL)] == [1, 1]

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", CREATOR, "--path-root", tmp_path)

    assert (code, err) == (0, "")
    report = json.loads(out)
    assert report["media_to_mark"] == 2
    assert report["groups"][0]["paths"] == [str(tmp_path / "downloads" / "a.jpg")]


@pytest.mark.parametrize("root", [[], ["--path-root", "anywhere"]])
def test_paths_recorded_on_another_system_are_refused(server, tmp_path, monkeypatch, capsys, root):
    """The scraper ran on another system than the command (the database is
    on a network): the files can't be looked at, and --path-root would put
    such a path somewhere it never was."""
    two_media(server, ELSEWHERE)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", CREATOR, "--apply", "--undo-dir", tmp_path, *root
    )

    assert (code, out) == (1, "")
    assert err.startswith("Recovery failed: The recorded path ")
    assert "a.jpg is a full path on another system than this one. Run this where the scraper runs" in err
    assert [row[4] for row in postgres_rows(URL)] == [1, 1]


def test_a_file_with_such_paths_is_read_as_before(tmp_path):
    rows = [(1, 1, ELSEWHERE, "a.jpg", 1, None, None), (2, 2, ELSEWHERE, "a.jpg", 1, None, None)]
    db = write_file(tmp_path / "1" / "user_data.db", CREATOR, NAME, rows)

    with pytest.raises(ValueError, match="path-root"):
        recover(db)
    assert recover(db, path_root=tmp_path)["media_to_mark"] == 2


# --- the command ---


@pytest.mark.parametrize(
    "args, said",
    [
        (["--postgres", "--creator", "a_creator", "some/user_data.db"], "give a user_data.db or --postgres, not both"),
        (["--postgres"], "--postgres needs --creator: the one creator to work on, by username or id"),
        (["--postgres", "--creator", ""], "--postgres needs --creator"),
        (["--creator", "a_creator", "some/user_data.db"], "--site, --creator and --undo-dir go with --postgres"),
        (["--site", "fansly", "some/user_data.db"], "--site, --creator and --undo-dir go with --postgres"),
        (["--undo-dir", "somewhere", "some/user_data.db"], "--site, --creator and --undo-dir go with --postgres"),
        (["--creator", "a_creator"], "--site, --creator and --undo-dir go with --postgres"),
        ([], "the following arguments are required: database, or --postgres"),
        (["--postgres", "--creator", "a_creator", "--site", "another"], "invalid choice: 'another'"),
        (["--postgres", "--creator", "a_creator", "--creator"], "expected one argument"),
        (
            ["--postgres", "--creator", "a_creator", "--undo", "undo.json", "--undo-dir", "somewhere"],
            "--undo-dir is where --apply writes a new undo file",
        ),
        (["--postgres", "--creator", "a_creator", "--apply"], "--postgres --apply needs --undo-dir"),
        # a path that is empty (a shell variable that isn't set) is not the current folder
        (["--postgres", "--creator", "a_creator", "--undo", ""], "error: --undo needs the path of an undo file"),
        (["--postgres", "--creator", "a_creator", "--undo", " ", "--apply"], "error: --undo needs the path of an undo file"),
        (["--postgres", "--creator", "a_creator", "--undo-dir", ""], "error: --undo-dir needs the path of a folder"),
        (
            ["--postgres", "--creator", "a_creator", "--apply", "--undo-dir", ""],
            "error: --undo-dir needs the path of a folder",
        ),
        # short forms that fit two options by now
        (["--postgres", "--creator", "a_creator", "--und", "undo.json"], "ambiguous option: --und could match --undo, --undo-dir"),
        (["some/user_data.db", "--p", "somewhere"], "ambiguous option: --p could match --path-root, --postgres"),
    ],
)
def test_cli_refuses_what_it_cant_make_sense_of(monkeypatch, capsys, args, said):
    monkeypatch.setattr(postgres, "Reader", lambda url: pytest.fail("nothing to connect for"))
    monkeypatch.setattr(postgres, "Writer", lambda url: pytest.fail("nothing to connect for"))

    code, out, err = cli(monkeypatch, capsys, *args)

    assert (code, out) == (2, "")
    assert said in err
    assert "s3cret-word" not in err and "db.example" not in err


@pytest.mark.parametrize("value", [None, "", "   "])
def test_cli_needs_the_address_in_its_own_environment(monkeypatch, capsys, value):
    monkeypatch.setattr(postgres, "Reader", lambda url: pytest.fail("nothing to connect to"))
    # an address the scraper's settings would give (from an env file) isn't seen
    monkeypatch.setattr(postgres, "url", lambda: URL)
    if value is not None:
        monkeypatch.setenv(postgres.URL_KEY, value)

    with pytest.raises(SystemExit) as stopped:
        recover_collisions.main(["--postgres", "--creator", NAME])

    said = capsys.readouterr()
    assert (stopped.value.code, said.out) == (2, "")
    assert "--postgres needs OFSC_DATABASE_URL set in the environment this is run in" in said.err
    assert "POSTGRESQL.md" in said.err


def test_only_the_commands_own_environment_is_asked(brought_in, tmp_path, monkeypatch, capsys):
    """Not the scraper's settings: they bring the scraper's environment and
    errors into the command."""

    def asked(*args, **kwargs):
        raise AssertionError("the scraper's settings were asked")

    monkeypatch.setattr(postgres.of_env, "getattr", asked)
    monkeypatch.setattr(postgres, "url", asked)
    monkeypatch.setattr(postgres, "enabled", asked)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, err) == (0, "")
    assert json.loads(out)["rows_marked"] == MARKED


def test_cli_given_a_file_works_on_the_file_and_says_so_while_postgresql_is_on(one_creator, monkeypatch, capsys):
    monkeypatch.setattr(postgres, "Reader", lambda url: pytest.fail("PostgreSQL wasn't asked for"))
    monkeypatch.setattr(postgres, "Writer", lambda url: pytest.fail("PostgreSQL wasn't asked for"))

    code, out, err = cli(monkeypatch, capsys, one_creator, "--apply")

    assert code == 0
    assert err == (
        "warning: PostgreSQL is on (OFSC_DATABASE_URL is set), but recover_collisions works on the"
        " user_data.db file it was given, not PostgreSQL. The file holds nothing scraped since"
        " PostgreSQL was turned on, and what is changed in it does not reach PostgreSQL. To work on"
        " PostgreSQL, give --postgres and --creator in place of the file. See POSTGRESQL.md.\n"
    )
    report = json.loads(out)
    assert report["rows_marked"] == MARKED
    # the undo file is beside the file, in the form it always had
    record = json.loads(Path(report["undo_file"]).read_text(encoding="utf-8"))
    assert set(record) == {"version", "database", "rows"} and record["version"] == 1
    assert Path(report["undo_file"]).parent == one_creator.parent


def test_given_a_file_an_undo_path_that_is_empty_fails_as_it_did(one_creator, capsys):
    """Only with --postgres is it refused before anything is looked at."""
    with pytest.raises(SystemExit) as stopped:
        recover_collisions.main([str(one_creator), "--undo", ""])

    said = capsys.readouterr()
    assert (stopped.value.code, said.out) == (1, "")
    assert said.err.startswith("Recovery failed: ") and said.err.count("\n") == 1


# --- what goes wrong ---


def test_a_read_that_fails_stops_the_run(brought_in, server, tmp_path, monkeypatch, capsys):
    server.fails_on = "medias"

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: Can't read the PostgreSQL database at db.example:5433/library."
        " (server closed the connection unexpectedly)\n"
    )
    assert server.events[-1] == ("close",)
    assert not undo_files(tmp_path / "undo")


@pytest.mark.parametrize("apply", [False, True])
def test_what_the_driver_says_never_repeats_the_address_or_its_password(tmp_path, monkeypatch, capsys, apply):
    """The driver quotes what it was given. The engine hides the address and
    its password in that, where it takes the driver's words."""
    psycopg = pytest.importorskip("psycopg")

    def refuses(url, **kwargs):
        raise psycopg.OperationalError(f'connection to "{url}" failed:\npassword s3cret-word was refused')

    monkeypatch.setattr(psycopg, "connect", refuses)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, *(["--apply", "--undo-dir", tmp_path] if apply else [])
    )

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: Can't use the PostgreSQL database at db.example:5433/library: the server can't be"
        ' reached. (connection to "{hidden}" failed: password {hidden} was refused)\n'
    )


@pytest.mark.parametrize("password", ["postgres", "undo", "creator"])
def test_the_commands_own_words_are_said_as_they_are_whatever_the_password(
    brought_in, server, tmp_path, monkeypatch, capsys, password
):
    """A password can be a word the command uses: `postgres` is Docker's
    usual one, and is in the undo file's name and in --postgres. Hiding it
    everywhere gave the path of a file that isn't there."""
    url = f"postgresql://scraper:{password}@db.example:5433/library"
    assert password in str(tmp_path / "undo" / "postgresql-onlyfans-10") + " --postgres --creator"
    server.commit_error = lost()

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo", url=url
    )

    (saved,) = undo_files(tmp_path / "undo")
    assert (code, out) == (1, "")
    assert err == f"Recovery failed: {LOST} {KEPT.format(saved)}\n"
    server.commit_error = None

    # an option, the name that was typed and a folder
    file_undo = tmp_path / "from-a-file.json"
    file_undo.write_text(json.dumps({"version": 1, "database": "user_data.db", "rows": []}), encoding="utf-8")
    for args, said in [
        (
            ["--creator", NAME, "--undo", file_undo],
            "Undo file was written for a user_data.db, not PostgreSQL: give that file in place of --postgres",
        ),
        (["--creator", password], f"PostgreSQL has no creator named {password} (looked in: onlyfans, fansly)"),
        (
            ["--creator", NAME, "--undo-dir", tmp_path / "undo" / password],
            f"The undo folder {tmp_path / 'undo' / password} isn't there, or isn't a folder",
        ),
    ]:
        code, out, err = cli(monkeypatch, capsys, "--postgres", *args, url=url)

        assert (code, out, err) == (1, "", f"Recovery failed: {said}\n")


def test_a_missing_driver_is_one_sentence(tmp_path, monkeypatch, capsys):
    real_import = builtins.__import__

    def no_driver(name, *args, **kwargs):
        if name.split(".")[0] in ("psycopg", "psycopg_pool"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_driver)

    for apply in ([], ["--apply", "--undo-dir", tmp_path]):
        code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", NAME, *apply)

        assert (code, out) == (1, "")
        assert err.startswith("Recovery failed: OFSC_DATABASE_URL is set, but the PostgreSQL driver isn't installed.")
        assert "[postgres]" in err and err.count("\n") == 1


@pytest.mark.parametrize("apply", [False, True])
def test_a_server_that_isnt_there_is_one_sentence(tmp_path, monkeypatch, capsys, apply):
    pytest.importorskip("psycopg")
    # Windows waits the whole time for a port nothing listens on
    monkeypatch.setattr(postgres, "CONNECT_TIMEOUT", 2)

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, *(["--apply", "--undo-dir", tmp_path] if apply else []),
        url=NOWHERE,
    )

    assert (code, out) == (1, "")
    assert err.startswith(
        "Recovery failed: Can't use the PostgreSQL database at 127.0.0.1:9/library: the server can't be reached. ("
    )
    assert err.count("\n") == 1
    assert "s3cret-word" not in err and "scraper" not in err


def test_an_address_the_driver_cant_read_is_said_without_quoting_it(tmp_path, monkeypatch, capsys):
    pytest.importorskip("psycopg")

    code, out, err = cli(
        monkeypatch, capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path,
        url="postgres//scraper:s3cret-word@db.example/library",
    )

    assert (code, out) == (1, "")
    assert err == (
        "Recovery failed: OFSC_DATABASE_URL isn't an address PostgreSQL can read. It should look like"
        " postgresql://user:password@host:5432/database.\n"
    )


# --- one creator's rows, changed (creator_rows) ---


def test_a_row_is_changed_only_while_it_holds_what_was_read(three_brought_in, server):
    before = held(server)
    here = before["onlyfans", "medias"][0][4]
    was = {"downloaded": 1, "directory": here, "filename": "shared.jpg", "size": 100, "hash": "hash-1"}

    with creator_rows.in_postgres(URL, ["onlyfans"], [NAME], write=True) as (rows,):
        # row 1 is this creator's first row; row 14 is the other creator's
        assert rows.change("medias", 1, {**was, "size": 101}, {"downloaded": 0}) is False
        assert rows.change("medias", 1, {**was, "hash": None}, {"downloaded": 0}) is False
        assert rows.change("medias", 1, {**was, "downloaded": 0}, {"downloaded": 0}) is False
        assert rows.change("medias", 14, was, {"downloaded": 0}) is False
        assert rows.change("medias", 999, was, {"downloaded": 0}) is False
        assert held(server) == before
        assert rows.change("medias", 1, was, {"downloaded": 0, "size": 5}) is True
        # an empty value is told from any other
        assert rows.change("medias", 12, {"directory": None, "filename": None}, {"filename": "found.jpg"}) is True
        rows.commit()

    after = held(server)
    assert after["fansly", "medias"] == before["fansly", "medias"]
    changed = [row for row in after["onlyfans", "medias"] if row not in before["onlyfans", "medias"]]
    assert [(row[0], row[5], row[6], row[11]) for row in changed] == [
        (1, "shared.jpg", 5, 0), (12, "found.jpg", None, 1),
    ]


def test_changes_are_kept_only_by_a_commit(brought_in, server):
    before = held(server)

    with creator_rows.in_postgres(URL, ["onlyfans"], [NAME], write=True) as (rows,):
        assert rows.change("medias", 4, {"downloaded": 1}, {"downloaded": 0}) is True
        assert held(server) != before

    assert held(server) == before
    assert server.events[-1] == ("close",)


@pytest.mark.parametrize(
    "was, to, said",
    [
        ({}, {"model_id": OTHER}, "a row's id and its creator can't be changed"),
        ({}, {"id": 99}, "a row's id and its creator can't be changed"),
        ({}, {}, "a row's id and its creator can't be changed"),
        ({}, {"no_such_column": 1}, "medias has no column no_such_column"),
        ({"size = size OR 1": 1}, {"downloaded": 0}, "medias has no column size = size OR 1"),
    ],
)
def test_a_change_cant_move_a_row_or_name_what_isnt_a_column(brought_in, server, was, to, said):
    before = held(server)

    with creator_rows.in_postgres(URL, ["onlyfans"], [NAME], write=True) as (rows,):
        with pytest.raises(ValueError) as raised:
            rows.change("medias", 1, was, to)

    assert str(raised.value) == said
    assert held(server) == before
    assert "change" not in [event[0] for event in server.events]


def test_the_change_names_the_site_the_creator_and_the_row():
    sent = []

    class Connection:
        def change(self, query, params):
            sent.append((query, params))
            return 1

    rows = creator_rows.PostgresRows(Connection(), "fansly", 77, {"medias": {"id", "model_id", "downloaded", "directory"}})

    assert rows.change("medias", 5, {"downloaded": 1, "directory": None}, {"downloaded": 0}) is True

    assert sent == [
        (
            "UPDATE fansly.medias SET downloaded = ? WHERE model_id = ? AND id = ?"
            " AND downloaded IS NOT DISTINCT FROM ? AND directory IS NOT DISTINCT FROM ?",
            [0, 77, 5, 1, None],
        )
    ]


# --- the connection (postgres.Writer), with the driver's connect stood in for ---


class Connection:
    """What Writer does to its connection, in order."""

    def __init__(self, fails=None, commit_fails=None):
        self.did = []
        self.fails = fails
        self.commit_fails = commit_fails

    def __setattr__(self, name, value):
        if name in ("read_only", "isolation_level"):
            self.did.append((name, value))
        object.__setattr__(self, name, value)

    def execute(self, query, params=None):
        if params is not None and self.fails:
            raise self.fails
        self.did.append(query if params is None else (query, params))
        return self

    rowcount = 3

    def commit(self):
        # the commits that set the connection up go through
        if self.commit_fails and str(self.did[-1][0]).startswith("UPDATE"):
            raise self.commit_fails
        self.did.append("commit")

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *error):
        return False

    def close(self):
        self.did.append("close")


def test_the_connection_can_change_rows_and_still_sees_the_database_at_one_moment(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    made = []
    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: made.append((url, kwargs, Connection())) or made[0][2])

    writer = postgres.Writer(URL)

    url, kwargs, conn = made[0]
    assert url == URL
    # values go in and come out as the engine's do
    assert kwargs["context"] is postgres._adapters()
    assert kwargs["cursor_factory"] is postgres._cursor_class()
    assert kwargs["row_factory"] is postgres.row_factory
    # set up as a Reader is, its timeouts with it, then opened for changes
    assert conn.did == [
        "SET TIME ZONE 'UTC'",
        "SET DateStyle TO 'ISO, YMD'",
        # how long a change waits for a row the scraper holds, and the
        # longest any one statement may take
        "SET lock_timeout = 30000",
        "SET statement_timeout = 300000",
        "commit",
        ("read_only", True),
        ("isolation_level", psycopg.IsolationLevel.REPEATABLE_READ),
        ("read_only", False),
    ]
    assert conn.read_only is False
    assert conn.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ
    # a server that went quiet is noticed, and nothing is kept on a pooler
    assert (kwargs["keepalives_idle"], kwargs["prepare_threshold"]) == (30, None)

    assert writer.change("UPDATE onlyfans.medias SET downloaded = ? WHERE id = ?", [0, 4]) == 3
    assert conn.did[-1] == ("UPDATE onlyfans.medias SET downloaded = ? WHERE id = ?", [0, 4])
    # nothing is kept until it is told to
    assert conn.did.count("commit") == 1
    writer.commit()
    assert conn.did.count("commit") == 2
    writer.close()
    writer.close()
    assert conn.did[-2:] == ["commit", "close"]


def test_a_change_another_program_got_in_the_way_of_says_so(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    for error, meanwhile in [
        (psycopg.errors.SerializationFailure(f"could not serialize access\ndue to concurrent update {URL}"), True),
        (psycopg.errors.LockNotAvailable("canceling statement due to lock timeout"), True),
        (psycopg.errors.DeadlockDetected("deadlock detected"), True),
        (psycopg.errors.InsufficientPrivilege("permission denied for table medias (password s3cret-word)"), False),
        (psycopg.OperationalError("server closed the connection unexpectedly"), False),
    ]:
        monkeypatch.setattr(psycopg, "connect", lambda url, error=error, **kwargs: Connection(fails=error))
        writer = postgres.Writer(URL)

        with pytest.raises(postgres.PostgresUnavailable) as raised:
            writer.change("UPDATE onlyfans.medias SET downloaded = ? WHERE id = ?", [0, 4])

        said = str(raised.value)
        assert isinstance(raised.value, postgres.ChangedMeanwhile) is meanwhile
        assert said.startswith(
            "Another program changed or is using the same rows of the PostgreSQL database at"
            " db.example:5433/library (is the scraper running?). Nothing was changed. ("
            if meanwhile
            else "Can't change the PostgreSQL database at db.example:5433/library. Nothing was changed. ("
        )
        assert "\n" not in said and "s3cret-word" not in said


def test_a_commit_that_fails_is_not_known_to_have_been_kept(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    lost = psycopg.OperationalError(f"connection to {URL} was lost")
    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: Connection(commit_fails=lost))
    writer = postgres.Writer(URL)
    writer.change("UPDATE onlyfans.medias SET downloaded = ? WHERE id = ?", [0, 4])

    with pytest.raises(postgres.Unconfirmed) as raised:
        writer.commit()

    assert str(raised.value) == (
        "The connection to the PostgreSQL database at db.example:5433/library was lost while the"
        " changes were being saved, so it isn't known whether they were. (connection to {hidden} was lost)"
    )
    assert raised.value.interrupted is False


@pytest.mark.parametrize("stopped_by, interrupted", [(KeyboardInterrupt, True), (SystemExit, False), (MemoryError, False)])
def test_a_commit_that_is_stopped_is_not_known_to_have_been_kept_either(monkeypatch, stopped_by, interrupted):
    """Ctrl-C while the server is asked to keep the changes: the driver
    passes it on whether the server had kept them or not, so it is no reason
    to think it hadn't."""
    psycopg = pytest.importorskip("psycopg")
    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: Connection(commit_fails=stopped_by()))
    writer = postgres.Writer(URL)
    writer.change("UPDATE onlyfans.medias SET downloaded = ? WHERE id = ?", [0, 4])

    with pytest.raises(postgres.Unconfirmed) as raised:
        writer.commit()

    assert str(raised.value) == (
        "This was stopped while the changes were being saved to the PostgreSQL database at"
        " db.example:5433/library, so it isn't known whether they were."
    )
    assert raised.value.interrupted is interrupted
    assert isinstance(raised.value.__cause__, stopped_by)


def test_a_connection_that_cant_be_opened_for_changes_is_closed(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    made = []

    class Refuses(Connection):
        def __setattr__(self, name, value):
            if (name, value) == ("read_only", False):
                raise psycopg.OperationalError("server closed the connection unexpectedly")
            super().__setattr__(name, value)

    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: made.append(Refuses()) or made[0])

    with pytest.raises(postgres.PostgresUnavailable) as raised:
        postgres.Writer(URL)

    assert "db.example:5433/library" in str(raised.value)
    assert made[0].did[-1] == "close"


# --- run on its own ---


def run_tool(code, **variables):
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), **variables},
    )


LOADED = (
    "print(sorted(name for name in sys.modules if name.split('.')[0]"
    " in ('rich', 'dotenv', 'aiohttp', 'psycopg', 'psycopg_pool')"
    " or name.startswith(('ofscraper.utils.settings', 'ofscraper.utils.console',"
    " 'ofscraper.utils.config'))))"
)


def test_given_a_file_the_driver_isnt_loaded(one_creator):
    result = run_tool(
        "import sys\n"
        "import ofscraper.commands.recover_collisions as tool\n"
        f"tool.main([{str(one_creator)!r}])\n"
        f"{LOADED}\n",
        **{postgres.URL_KEY: URL},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "[]"
    assert json.loads(result.stdout.rsplit("\n", 2)[0])["media_to_mark"] == TO_MARK
    assert result.stderr.startswith("warning: PostgreSQL is on")


@pytest.mark.parametrize("apply", [False, True])
def test_working_on_postgresql_doesnt_load_the_scraper(tmp_path, apply):
    """Nor does a setting the scraper would stop on stop it."""
    pytest.importorskip("psycopg")
    apply = ["--apply", "--undo-dir", str(tmp_path)] if apply else []
    result = run_tool(
        "import sys\n"
        "import ofscraper.commands.recover_collisions as tool\n"
        # Windows waits the whole time for a port nothing listens on
        "tool.postgres.CONNECT_TIMEOUT = 2\n"
        "try:\n"
        f"    tool.main(['--postgres', '--creator', 'a_creator', *{apply!r}])\n"
        "except SystemExit as stopped:\n"
        "    code = stopped.code\n"
        f"{LOADED}\n"
        "sys.exit(code)",
        OFSC_DOWNLOAD_SEM_DEFAULT="many",
        **{postgres.URL_KEY: NOWHERE},
    )

    assert result.returncode == 1, result.stderr
    # the driver, and nothing of the scraper's
    loaded = {name.split(".")[0] for name in ast.literal_eval(result.stdout)}
    assert loaded == {"psycopg", "psycopg_pool"}
    assert result.stderr.startswith("Recovery failed: Can't use the PostgreSQL database at 127.0.0.1:9/library")
    assert "Traceback" not in result.stderr and "s3cret-word" not in result.stderr
