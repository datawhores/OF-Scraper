"""move_creator_files on PostgreSQL (#644): what needs no server.

The server is a stand-in (postgres_stand_in.py) that hands rows over as the
real driver does; the tests that use it need the driver installed. The
`check_...` functions are run again against a real server by
test_move_creator_files_postgres_live.py, in CI. The files are real ones,
under pytest's tmp_path.
"""

import builtins
import json
from contextlib import closing
from pathlib import Path

import pytest

import ofscraper.commands.move_creator_files as tool
import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
from test.test_move_creator_files import AFTER, CREATOR, NEW, OLD, Library, listing, split_files, under

URL = "postgresql://scraper:s3cret-word@db.example:5433/library"
# a second creator of the same site, who has had the same two names
OTHER = 20
COLUMNS = ["media_id", "post_id", "directory", "filename", "size", "downloaded", "hash", "model_id"]
WHO = {"site": "onlyfans", "model_id": CREATOR}


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    monkeypatch.delenv(tool.PLACEHOLDER_KEY, raising=False)


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


@pytest.fixture
def one_creator(tmp_path):
    """A creator whose files are split over the folders of two names, in
    their file under .data."""
    return split_files(Library(tmp_path))


@pytest.fixture
def three_creators(one_creator, tmp_path):
    """Two more creators who have had the same two names, with files of
    their own in the same folders: a second creator of the site, and the
    other site's creator with the first one's id."""
    Library(tmp_path, model_id=OTHER).add(f"{OLD}/Posts/Images", "second.jpg")
    Library(tmp_path, site="fansly", under="Fansly").add(f"{OLD}/Posts/Images", "namesake.jpg")
    return one_creator


def file_rows(db):
    with closing(creator_rows.FileRows(db)) as rows:
        return [tuple(row) for row in rows.select("medias", COLUMNS)]


def postgres_rows(database_url, creator=CREATOR, site="onlyfans"):
    with creator_rows.in_postgres(database_url, [site]) as found:
        (rows,) = [rows for rows in found if rows.model_id == creator]
        return [tuple(row) for row in rows.select("medias", COLUMNS)]


def recorded(rows):
    """Where each of these rows says its file is."""
    return [str(Path(row[2], row[3])) for row in rows]


def held(server):
    """Every row the stand-in holds, as it holds it."""
    return {
        (schema, table): server.db.execute(f"SELECT * FROM {schema}.{table} ORDER BY 1").fetchall()
        for schema in sorted(server.schemas)
        for table in postgres.TABLE_COLUMNS
    }


def check_same_move(database_url, library):
    """A file and the database it was brought into give one preview, and
    the move ends the same whichever it is made through. The files are the
    same ones for both, so the second to move finds them moved."""
    before = file_rows(library.db)
    tree = listing(library.root)
    assert postgres_rows(database_url) == before

    from_file = tool.on_file(library.db)
    from_database = tool.on_postgres(database_url, str(CREATOR))

    assert from_database == from_file
    assert (from_file["to_move"], from_file["to"], from_file["creator"]) == (4, NEW, WHO)
    # a preview changes nothing
    assert postgres_rows(database_url) == file_rows(library.db) == before
    assert listing(library.root) == tree

    in_database = tool.on_postgres(database_url, OLD, apply=True)

    assert (in_database["moved"], in_database["rows_changed"], in_database["left"]) == (4, 4, [])
    after = postgres_rows(database_url)
    assert recorded(after) == under(library, NEW, *AFTER)
    # nothing else of a row changed
    assert [row[:2] + row[3:] for row in after] == [row[:2] + row[3:] for row in before]
    assert all(Path(path).is_file() for path in recorded(after))
    again = tool.on_postgres(database_url, NEW, apply=True)
    assert (again["to_move"], again["already_there"], again["rows_changed"]) == (0, 0, 0)

    # the file finds its files at their new places
    in_file = tool.on_file(library.db, apply=True)
    assert (in_file["moved"], in_file["already_there"], in_file["rows_changed"]) == (0, 4, 4)
    assert file_rows(library.db) == after


def check_only_that_creator(database_url, snapshot, schema, library):
    """Of everything the database holds, --apply changes the folder of the
    one creator's rows in the one site, and of every file only that
    creator's are moved. `snapshot` gives every row held:
    {(schema, table): rows}."""
    before = snapshot()
    tree = listing(library.root)
    folder = postgres.TABLE_COLUMNS["medias"].index("directory")
    creator = postgres.TABLE_COLUMNS["medias"].index("model_id")
    # the other creator of the site has a row beside this one's
    assert len(before[schema, "medias"]) == 5 + 1

    result = tool.on_postgres(database_url, str(CREATOR), site="onlyfans", apply=True)

    assert (result["moved"], result["rows_changed"], result["creator"]) == (4, 4, WHO)
    after = snapshot()
    assert set(after) == set(before)
    changed = 0
    for key, rows in before.items():
        assert len(after[key]) == len(rows)
        for was, now in zip(rows, after[key]):
            if was == now:
                continue
            assert key == (schema, "medias") and was[creator] == CREATOR
            assert was[:folder] + was[folder + 1:] == now[:folder] + now[folder + 1:]
            assert Path(now[folder]).relative_to(library.root / NEW) == Path(was[folder]).relative_to(library.root / OLD)
            changed += 1
    assert changed == 4
    # the others' files are where they were
    now = listing(library.root)
    for theirs in (f"{OLD}/Posts/Images/second.jpg", f"{OLD}/Posts/Images/namesake.jpg", f"{OLD}/Posts/Images/notes.txt"):
        assert now[theirs] == tree[theirs]


def test_the_same_rows_give_the_same_move_from_either(one_creator, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    check_same_move(URL, one_creator)


def test_only_that_creators_rows_and_files_are_touched(three_creators, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    check_only_that_creator(URL, lambda: held(server), "onlyfans", three_creators)


def test_without_apply_the_database_is_only_read_and_nothing_is_moved(one_creator, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    before, tree = held(server), listing(one_creator.root)
    del server.events[:]

    report = tool.on_postgres(URL, OLD)

    assert (report["applied"], report["to_move"], report["moved"]) == (False, 4, 0)
    assert not [event for event in server.events if event[0] in ("open for changes", "change", "commit")]
    assert held(server) == before and listing(one_creator.root) == tree


def test_a_commit_that_didnt_arrive_is_finished_by_running_it_again(one_creator, server, tmp_path, capsys):
    import psycopg

    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    before = held(server)
    server.commit_error = psycopg.OperationalError("the connection is closed")

    with pytest.raises(postgres.Unconfirmed):
        tool.on_postgres(URL, OLD, apply=True)

    # the files are at their new places, and no row says so
    assert held(server) == before
    assert capsys.readouterr().err == tool.AGAIN.format(4) + "\n"
    server.commit_error = None

    report = tool.on_postgres(URL, OLD, apply=True)

    assert (report["already_there"], report["moved"], report["rows_changed"], report["left"]) == (4, 0, 4, [])
    assert recorded(postgres_rows(URL)) == under(one_creator, NEW, *AFTER)


def test_a_row_changed_meanwhile_stops_the_run_with_no_row_changed(one_creator, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    # the scraper saves a download over the row of the first file to be moved
    server.before_change = lambda: server.elsewhere(
        "UPDATE onlyfans.medias SET directory = 'somewhere else' WHERE filename = 'd.jpg'"
    )
    before = postgres_rows(URL)

    with pytest.raises(postgres.ChangedMeanwhile) as stopped:
        tool.on_postgres(URL, OLD, apply=True)

    assert str(stopped.value) == tool.MEANWHILE
    after = postgres_rows(URL)
    assert after[3][2] == "somewhere else" and after[:3] + after[4:] == before[:3] + before[4:]


def cli(monkeypatch, capsys, *args):
    """The command, with the address in its environment for the call only:
    (exit code, stdout, stderr)."""
    capsys.readouterr()
    with monkeypatch.context() as patch:
        patch.setenv(postgres.URL_KEY, URL)
        try:
            code = tool.main([str(arg) for arg in args]) or 0
        except SystemExit as stopped:
            code = stopped.code
    said = capsys.readouterr()
    return code, said.out, said.err


def test_cli_names_one_creator_or_changes_nothing(three_creators, server, tmp_path, monkeypatch, capsys):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    before, tree = held(server), listing(three_creators.root)

    # three creators have had the name
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", OLD, "--apply")
    assert (code, out) == (1, "")
    assert err.startswith(f"Move failed: PostgreSQL has more than one creator named {OLD}: onlyfans 10 (")
    assert err.endswith("Give --site, or a username or id that only one of them has\n")
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", "nobody", "--apply")
    assert (code, out, err) == (1, "", "Move failed: PostgreSQL has no creator named nobody (looked in: onlyfans, fansly)\n")
    assert cli(monkeypatch, capsys, three_creators.db, "--postgres", "--creator", OLD)[0] == 2
    assert cli(monkeypatch, capsys, "--postgres")[0] == 2
    assert held(server) == before and listing(three_creators.root) == tree

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", CREATOR, "--site", "fansly", "--apply")

    assert (code, err) == (0, "")
    report = json.loads(out)
    assert (report["creator"], report["moved"], report["rows_changed"]) == ({"site": "fansly", "model_id": CREATOR}, 1, 1)
    assert postgres_rows(URL) == file_rows(three_creators.db)


def test_a_missing_driver_is_one_sentence(monkeypatch, capsys):
    real_import = builtins.__import__

    def no_driver(name, *args, **kwargs):
        if name.split(".")[0] in ("psycopg", "psycopg_pool"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_driver)

    for apply in ([], ["--apply"]):
        code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", "someone", *apply)

        assert (code, out) == (1, "")
        assert err.startswith("Move failed: OFSC_DATABASE_URL is set, but the PostgreSQL driver isn't installed.")
        assert err.count("\n") == 1
