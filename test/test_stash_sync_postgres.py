"""stash_sync reading PostgreSQL (#631): everything that needs no server.

The server is a stand-in (postgres_stand_in.py) that hands rows over as the
real driver does; the tests that use it need the driver installed. The
`check_...` functions are run again against a real server by
test_stash_sync_postgres_live.py, in CI.
"""

import ast
import asyncio
import builtins
import copy
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_stash_sync import (  # noqa: F401  (the fixtures)
    DM_CREATOR_ID,
    OF_ID,
    OF_USER,
    FakeStash,
    fansly,
    fansly_library,
    library,
    of_item,
    stash_server,
)

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.operations as operations
import ofscraper.db.postgres as postgres
import ofscraper.utils.settings as settings
from ofscraper.commands import stash_sync
from ofscraper.commands.stash_sync import read_model, sync
from ofscraper.db.operations_.media import batch_mediainsert, mark_media_as_downloaded, mediaCreate
from ofscraper.db.operations_.messages import messagesCreate
from ofscraper.db.operations_.others import schemaCreate, siteInsert
from ofscraper.db.operations_.posts import postCreate
from ofscraper.db.operations_.profile import profilesCreate

URL = "postgresql://scraper:s3cret-word@db.example:5433/library"
ROOT = Path(__file__).resolve().parents[1]
BOTH = ["onlyfans", "fansly"]
# a second OnlyFans creator, and a Fansly creator with an OnlyFans creator's id
SECOND, SECOND_NAME = 456, "second_creator"
SAME_ID, SAME_ID_NAME = 123, "fansly_namesake"
# a server nothing listens on
NOWHERE = "postgresql://scraper:s3cret-word@127.0.0.1:9/library"


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


@pytest.fixture
def server(monkeypatch):
    """A stand-in for the PostgreSQL server, which postgres.Reader reads."""
    pytest.importorskip("psycopg")
    from test.postgres_stand_in import Server

    server = Server()
    monkeypatch.setattr(postgres, "Reader", server.reader)
    yield server
    server.close()


def cli(monkeypatch, capsys, *args, url=URL):
    """The command, with the address in its environment for the call only:
    (exit code, stdout, stderr)."""
    capsys.readouterr()
    with monkeypatch.context() as patch:
        patch.setenv(postgres.URL_KEY, url)
        try:
            code = stash_sync.main(list(args))
        except SystemExit as stopped:
            code = stopped.code
    said = capsys.readouterr()
    return code, said.out, said.err


class Recording(FakeStash):
    """FakeStash that keeps every call it was sent."""

    def __init__(self, files=()):
        super().__init__()
        self.calls = []
        for kind, path in files:
            self.add(kind, path)

    def call(self, query, variables=None):
        self.calls.append((query, copy.deepcopy(variables)))
        return super().call(query, variables)


def state(stash):
    return copy.deepcopy(
        (stash.items, stash.galleries, stash.entities, stash.disambiguation, stash.created, stash.updates)
    )


def from_postgres(database_url, stash, sites=BOTH, wanted=(), **options):
    with creator_rows.in_postgres(database_url, sites, wanted) as creators:
        read = stash_sync.read_creators(creators)
    return sync((), stash, read=read, **options)


def without_sources(report):
    """A report without where each creator's rows were: a file's path, or
    PostgreSQL."""
    return {**report, "models": [{k: v for k, v in m.items() if k != "database"} for m in report["models"]]}


# --- the creators ---


def write_file(db, model_id, username, posts=(), messages=(), medias=(), site=None):
    """A user_data.db with the scraper's own tables and these rows."""
    db.parent.mkdir(parents=True)
    with closing(sqlite3.connect(db)) as conn, conn:
        for create in (mediaCreate, postCreate, messagesCreate, profilesCreate, schemaCreate):
            conn.execute(create)
        if site:
            conn.execute(siteInsert, (site,))
        conn.execute("INSERT INTO profiles (user_id, username) VALUES (?, ?)", (model_id, username))
        conn.executemany(
            f"INSERT INTO posts (post_id, text, model_id) VALUES (?, ?, {model_id})", posts
        )
        conn.executemany(
            f"INSERT INTO messages (post_id, text, group_id, model_id) VALUES (?, ?, ?, {model_id})", messages
        )
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, directory, filename, api_type, media_type, downloaded,"
            f" preview, posted_at, created_at, model_id) VALUES (?,?,?,?,?,?,?,?,?,?,{model_id})",
            medias,
        )
    return db


def save_onlyfans(monkeypatch, media_dir, db=None):
    """A timeline post, a message that was also bought, and a post seen only
    as a purchase, saved by the scraper's own code: into the file `db`, or,
    without one, wherever the scraper saves (PostgreSQL when that is on)."""
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    message = of_item(3001, 4001, responseType="message", fromUser={"id": OF_ID})

    async def write():
        await operations.table_init_create(model_id=OF_ID, username=OF_USER)
        timeline = posts_.Post(of_item(1001, 2001, responseType="post"), OF_ID, OF_USER, "Timeline")
        messages = posts_.Post(message, OF_ID, OF_USER)
        bought = [posts_.Post(copy.deepcopy(message), OF_ID, OF_USER, responsetype="Paid"),
                  posts_.Post(of_item(5001, 6001, responseType="post"), OF_ID, OF_USER, responsetype="Paid")]
        await operations.make_post_table_changes([timeline, *bought], model_id=OF_ID, username=OF_USER)
        await operations.make_messages_table_changes([messages], model_id=OF_ID, username=OF_USER)
        media = [m for p in (timeline, messages, *bought) for m in p.all_media]
        await batch_mediainsert(media, model_id=OF_ID, username=OF_USER, downloaded=False)
        for m in media:
            await mark_media_as_downloaded(m, model_id=OF_ID, username=OF_USER,
                                           filepath=media_dir / f"{m.id}.jpg", downloaded=True)

    with monkeypatch.context() as patch:
        patch.setattr(settings, "get_settings", lambda: Stub(site="onlyfans", after=None, post_id=None))
        patch.setattr(operations, "create_backup", lambda *a, **k: None)
        if db is not None:
            db.parent.mkdir(parents=True)
            patch.setattr(placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db)
        asyncio.run(write())
    return [("image", str(media_dir / "2001.jpg")), ("image", str(media_dir / "4001.jpg"))]


@pytest.fixture
def more_creators(tmp_path):
    """Two more files under .data: an OnlyFans creator whose rows clash with
    the `library` creator's in every way shared tables allow, and a Fansly
    creator with that creator's id. Returns the files to have in Stash."""
    media_dir = str(tmp_path / "second")
    day = "2025-03-01T10:00:00+00:00"
    write_file(
        tmp_path / ".data" / str(SECOND) / "user_data.db",
        SECOND,
        SECOND_NAME,
        # 1001 and 2002 are the other creator's ids too
        posts=[(1001, "The second creator's own post"), (7001, ""), (7002, None), (2002, "a post, not a message")],
        messages=[(8001, "<p>from the second</p>", None)],
        medias=[
            (11, 1001, media_dir, "a.jpg", "Timeline", "Images", 1, 0, day, day),
            (12, 7001, media_dir, "b.mp4", "Timeline", "Videos", 1, 1, None, "2025-03-02T10:00:00.250000+00:00"),
            # one file, saved twice: the row saved first names its type
            (13, 8001, media_dir, "c.jpg", "Messages", "Images", 1, 0, "2025-03-04T10:00:00+00:00", day),
            (13, 7002, media_dir, "c.jpg", "Timeline", "Videos", 1, 0, "2025-03-03T10:00:00+00:00", day),
            (14, 7002, media_dir, "", "Timeline", "Images", 1, 0, day, day),
            (15, 7002, media_dir, None, "Timeline", "Images", 1, 0, day, day),
            (16, 2002, None, "no_folder.jpg", "Timeline", "Images", 1, None, None, day),
            (17, 7002, media_dir, "not_downloaded.jpg", "Timeline", "Images", 0, 0, day, day),
            (18, 7002, media_dir, "never_tried.jpg", "Timeline", "Images", None, 0, day, day),
            (19, "feedc0de", media_dir, "avatar.jpg", "Profile", "Images", 1, 0, None, None),
        ],
    )
    fansly_dir = str(tmp_path / "namesake")
    write_file(
        tmp_path / ".data" / "Fansly" / str(SAME_ID) / "user_data.db",
        SAME_ID,
        SAME_ID_NAME,
        posts=[(1001, "A Fansly post #Tagged with @second_creator")],
        messages=[(9001, "a Fansly message", 9100), (9002, "one without its conversation", None)],
        medias=[
            (21, 1001, fansly_dir, "f.jpg", "Timeline", "Images", 1, 1, day, day),
            (22, 9001, fansly_dir, "g.mp4", "Messages", "Videos", 1, 0, day, day),
            (23, 9002, fansly_dir, "h.jpg", "Messages", "Images", 1, 0, day, day),
        ],
        site="fansly",
    )
    return [
        ("image", os.path.join(media_dir, "a.jpg")),
        ("scene", os.path.join(media_dir, "b.mp4")),
        ("image", os.path.join(media_dir, "c.jpg")),
        ("image", "no_folder.jpg"),
        ("image", os.path.join(fansly_dir, "f.jpg")),
        ("scene", os.path.join(fansly_dir, "g.mp4")),
    ]


@pytest.fixture
def everything(library, fansly_library, more_creators, tmp_path, monkeypatch):
    """Five creators' files under one .data folder, written by hand and by
    the scraper's own code for each site: (the folder, the files Stash has).
    One file of each creator is left out of Stash."""
    _, of_dir = library
    _, _, fansly_files = fansly_library
    paid = save_onlyfans(monkeypatch, tmp_path / "of", tmp_path / ".data" / str(OF_ID) / "user_data.db")
    in_stash = [
        ("scene", str(of_dir / "post.mp4")),
        ("image", str(of_dir / "post.jpg")),
        ("image", str(of_dir / "msg.jpg")),
        *paid,
        *[(kind, path) for path, kind in fansly_files[1:]],
        *more_creators,
    ]
    return tmp_path / ".data", in_stash


PERFORMERS = ["creator", OF_USER, SECOND_NAME, "samplecreator2", SAME_ID_NAME]


# --- the same rows, the same sync ---


def check_same_sync(database_url, data, in_stash, apply):
    """Files and the database they were brought into give one sync."""
    files, database = Recording(in_stash), Recording(in_stash)

    from_files = sync([data], files, apply=apply)
    from_database = from_postgres(database_url, database, apply=apply)

    assert [m["performer"] for m in from_files["models"]] == PERFORMERS
    assert without_sources(from_database) == without_sources(from_files)
    assert [m["database"] for m in from_database["models"]] == [
        "PostgreSQL: onlyfans, creator 123",
        f"PostgreSQL: onlyfans, creator {OF_ID}",
        f"PostgreSQL: onlyfans, creator {SECOND}",
        f"PostgreSQL: fansly, creator {DM_CREATOR_ID}",
        f"PostgreSQL: fansly, creator {SAME_ID}",
    ]
    # every question and every change Stash was sent, in order
    assert database.calls == files.calls
    assert state(database) == state(files)
    # and it was a sync worth comparing
    totals = from_files["totals"]
    assert totals["not_in_stash"] >= 5 and totals["unsupported_type"] == 1
    assert totals["updated" if apply else "to_update"] >= 12
    assert totals["galleries_created" if apply else "galleries_to_create"] >= 6


def with_moments(entry):
    """An entry with its dates as the moments they name. The text differs
    between the two and the moment doesn't: PostgreSQL writes a fraction of a
    second without its last zeros (.25 where a file has .250000)."""
    return {
        **entry,
        "posts": [(datetime.fromisoformat(posted) if posted else posted, post_id) for posted, post_id in entry["posts"]],
    }


def check_own_rows(database_url, data):
    """Each creator's rows, out of tables every creator shares, are the rows
    of that creator's file."""
    expected = []
    for rows in creator_rows.files([data]):
        with closing(rows):
            expected.append((rows.site, read_model(rows.path, rows.site)))

    with creator_rows.in_postgres(database_url, BOTH) as creators:
        found = [(rows.site, stash_sync.read_rows(rows, rows.site)) for rows in creators]

    assert len(found) == len(expected)
    for (site, (username, entries)), (file_site, (file_username, file_entries)) in zip(found, expected):
        assert (site, username) == (file_site, file_username)
        assert [entry["path"] for entry in entries] == [entry["path"] for entry in file_entries]
        for entry, file_entry in zip(entries, file_entries):
            assert with_moments(entry) == with_moments(file_entry)
    assert [(site, username) for site, (username, _) in found] == list(
        zip(["onlyfans", "onlyfans", "onlyfans", "fansly", "fansly"], PERFORMERS)
    )
    # the post three creators number 1001 is each one's own
    texts = {
        username: {f["meta"]["details"] for f in files if f["meta"].get("code") in ("1001", "21")}
        for _, (username, files) in found
    }
    assert texts["creator"] == {"First line & more\nsecond line"}
    assert texts[OF_USER] == {"caption 1001"}
    assert texts[SECOND_NAME] == {"The second creator's own post"}
    assert texts[SAME_ID_NAME] == {"A Fansly post #Tagged with @second_creator"}


def check_values(database_url, folder):
    """What comes out for the `more_creators` OnlyFans creator: yes/no
    columns, ids kept as text, dates and empty values, as a file gives them."""
    with creator_rows.in_postgres(database_url, ["onlyfans"]) as creators:
        (rows,) = creators
        media = rows.select(
            "medias",
            ["media_id", "post_id", "directory", "filename", "downloaded", "preview",
             "COALESCE(posted_at, created_at)", "model_id"],
        )
        downloaded = rows.select("medias", ["media_id"], "downloaded = TRUE AND filename IS NOT NULL AND filename != ''")
        posts = rows.select("posts", ["post_id", "text"])
        profiles = rows.select("profiles", ["username"])
        columns = rows.columns("medias")
        assert rows.columns("no_such_table") == set()

    by_id = {row[0]: row for row in media}
    assert list(by_id) == [11, 12, 13, 14, 15, 16, 17, 18, 19]
    assert tuple(by_id[11]) == (11, 1001, folder, "a.jpg", 1, 0, "2025-03-01T10:00:00+00:00", SECOND)
    assert [type(value) for value in by_id[11]] == [int, int, str, str, int, int, str, int]
    # no posted_at: the day it was made, with its fraction of a second
    assert tuple(by_id[12][4:7]) == (1, 1, "2025-03-02T10:00:00.25+00:00")
    assert by_id[15][3] is None and by_id[14][3] == ""
    assert by_id[16][2] is None and by_id[16][5] is None
    assert by_id[17][4] == 0 and by_id[18][4] is None
    # a profile picture's post id is a hash, and stays text
    assert tuple(by_id[19][:2]) == (19, "feedc0de") and by_id[19][6] is None
    assert [tuple(row) for row in downloaded] == [(11,), (12,), (13,), (13,), (16,), (19,)]
    assert [tuple(row) for row in posts] == [
        (1001, "The second creator's own post"), (7001, ""), (7002, None), (2002, "a post, not a message"),
    ]
    assert [tuple(row) for row in profiles] == [(SECOND_NAME,)]
    assert {"id", "media_id", "posted_at", "skip_permanent"} <= columns


def check_oldest_first(database_url):
    """The `more_creators` OnlyFans creator's files, in the order they were saved."""
    database = Recording()

    report = from_postgres(database_url, database, sites=["onlyfans"])

    assert [Path(p).name for p in report["models"][0]["not_in_stash_sample"]] == [
        "a.jpg", "b.mp4", "c.jpg", "no_folder.jpg", "avatar.jpg",
    ]
    # c.jpg was saved first as an image
    assert report["models"][0].get("unsupported_type") is None
    assert not any("findScenes" in query and variables["path"].endswith("c.jpg") for query, variables in database.calls)


# the two dates a file and PostgreSQL give differently: posted_at,
# created_at, the day from the file, the day from PostgreSQL
DATES = [
    # a file keeps the text the scraper saved, with its offset; PostgreSQL
    # keeps the moment, and gives it in UTC
    ("2025-03-01T23:30:00-05:00", "2025-03-01T23:30:00-05:00", "2025-03-01", "2025-03-02"),
    # to a file an empty text is a date, so the day the media was made isn't
    # used in its place; brought into PostgreSQL it is no date
    ("", "2025-03-01T10:00:00+00:00", None, "2025-03-01"),
]


def dated_file(tmp_path, posted, made):
    return write_file(
        tmp_path / ".data" / "5" / "user_data.db", 5, "a_creator",
        posts=[(1, "a post")],
        medias=[(1, 1, "folder", "one.jpg", "Timeline", "Images", 1, 0, posted, made)],
    )


def renamed_file(tmp_path):
    """A creator who changed username: both are saved, the new one last."""
    db = write_file(
        tmp_path / ".data" / "5" / "user_data.db", 5, "Former_Name",
        posts=[(1, "a post")],
        medias=[(1, 1, "folder", "one.jpg", "Timeline", "Images", 1, 0, None, None)],
    )
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO profiles (user_id, username) VALUES (5, 'Current_Name')")
    return db


def check_username(database_url, db):
    """The username saved last is the creator's, from a file and from
    PostgreSQL. Any they have had finds them, in any case."""
    with creator_rows.in_postgres(database_url, BOTH) as creators:
        from_database = [stash_sync.read_rows(rows)[0] for rows in creators]

    assert read_model(db)[0] == "Current_Name"
    assert from_database == ["Current_Name"]
    for name in ("current_name", "FORMER_NAME", "5"):
        with creator_rows.in_postgres(database_url, BOTH, [name]) as creators:
            assert [rows.model_id for rows in creators] == [5]


def seven_creators(tmp_path):
    """Seven creators of one site, so that each read is run seven times:
    (the folder, the files Stash has)."""
    day = "2025-03-01T10:00:00+00:00"
    in_stash = []
    for creator in range(1, 8):
        write_file(
            tmp_path / ".data" / str(creator) / "user_data.db", creator, f"creator_{creator}",
            posts=[(1, f"a post of creator {creator}")],
            messages=[(2, "a message", None)],
            medias=[
                (1, 1, "folder", f"{creator}.jpg", "Timeline", "Images", 1, 0, day, day),
                (2, 2, "folder", f"{creator}.mp4", "Messages", "Videos", 1, 0, day, day),
            ],
        )
        in_stash += [("image", os.path.join("folder", f"{creator}.jpg")), ("scene", os.path.join("folder", f"{creator}.mp4"))]
    return tmp_path / ".data", in_stash


def check_seven_creators(database_url, data, in_stash, while_open=lambda creators: None):
    """The seventh creator is read as the first is. Returns what
    `while_open` found while the connection was still open."""
    files, database = Recording(in_stash), Recording(in_stash)
    with creator_rows.in_postgres(database_url, ["onlyfans"]) as creators:
        read = stash_sync.read_creators(creators)
        found = while_open(creators)

    from_database = sync((), database, read=read, apply=True)
    from_files = sync([data], files, apply=True)

    assert [m["performer"] for m in from_database["models"]] == [f"creator_{n}" for n in range(1, 8)]
    assert without_sources(from_database) == without_sources(from_files)
    assert from_files["totals"] == {"files": 14, "updated": 14}
    assert database.calls == files.calls
    return found


def check_date(database_url, db, from_a_file, from_postgresql):
    with creator_rows.in_postgres(database_url, BOTH) as creators:
        _, (from_database,) = stash_sync.read_rows(creators[0])

    assert read_model(db)[1][0]["meta"].get("date") == from_a_file
    assert from_database["meta"].get("date") == from_postgresql


@pytest.mark.parametrize("apply", [False, True])
def test_the_same_rows_give_the_same_sync_from_either(everything, server, tmp_path, apply):
    data, in_stash = everything
    server.bring_in(data, tmp_path / "staging")

    check_same_sync(URL, data, in_stash, apply)


def test_each_creator_gets_only_their_own_rows(everything, server, tmp_path):
    data, _ = everything
    server.bring_in(data, tmp_path / "staging")

    check_own_rows(URL, data)


def test_the_values_are_the_ones_a_file_gives(more_creators, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    check_values(URL, str(tmp_path / "second"))


def test_rows_come_oldest_first(more_creators, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    check_oldest_first(URL)


@pytest.mark.parametrize("posted, made, from_a_file, from_postgresql", DATES)
def test_the_two_dates_postgresql_gives_differently(tmp_path, server, posted, made, from_a_file, from_postgresql):
    db = dated_file(tmp_path, posted, made)
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    check_date(URL, db, from_a_file, from_postgresql)


def test_the_username_saved_last_is_the_creators(tmp_path, server):
    db = renamed_file(tmp_path)
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    # a name saved later still, for a creator with nothing else, isn't this one's
    server.insert("onlyfans", "profiles", ["user_id", "username"], [(6, "someone_else")])

    check_username(URL, db)


def test_the_seventh_creator_of_a_site_is_read_as_the_first(tmp_path, server):
    data, in_stash = seven_creators(tmp_path)
    server.bring_in(data, tmp_path / "staging")

    check_seven_creators(URL, data, in_stash)


def test_files_are_closed_once_they_are_read(library, monkeypatch):
    db, _ = library
    opened = []
    connect = sqlite3.connect

    def keep(*args, **kwargs):
        opened.append(connect(*args, **kwargs))
        return opened[-1]

    monkeypatch.setattr(creator_rows.sqlite3, "connect", keep)
    try:
        read_model(db)
        stash_sync.site_of(db)
        sync([db], Recording())

        assert len(opened) == 3
        for conn in opened:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                conn.execute("SELECT 1")
    finally:
        for conn in opened:
            conn.close()


def test_a_database_made_before_a_column_was_added_reads_as_a_file_from_then(tmp_path, server):
    server.make("fansly", without={("messages", "group_id"), ("posts", "purchase_type")})
    server.insert("fansly", "profiles", ["user_id", "username"], [(7, "an_old_one")])
    server.insert("fansly", "messages", ["post_id", "text", "model_id"], [(9001, "a message", 7)])
    server.insert(
        "fansly", "medias",
        ["media_id", "post_id", "directory", "filename", "api_type", "media_type", "downloaded", "posted_at", "model_id"],
        [(1, 9001, "folder", "m.jpg", "Messages", "Images", True, "2025-03-01T10:00:00+00:00", 7)],
    )

    with creator_rows.in_postgres(URL, BOTH) as creators:
        username, (entry,) = stash_sync.read_rows(creators[0], "fansly")

    assert username == "an_old_one"
    # no conversation id, so no link yet
    assert entry["meta"]["details"] == "a message" and "url" not in entry["meta"]


# --- which creators ---


def creators_of(sites=BOTH, wanted=(), database_url=URL):
    with creator_rows.in_postgres(database_url, sites, wanted) as creators:
        return [(rows.site, rows.model_id) for rows in creators]


def test_every_creator_of_both_sites_unless_told(more_creators, library, server, tmp_path):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    assert creators_of() == [("onlyfans", 123), ("onlyfans", SECOND), ("fansly", SAME_ID)]
    assert creators_of(["fansly"]) == [("fansly", SAME_ID)]
    assert creators_of(["fansly", "onlyfans"])[0] == ("fansly", SAME_ID)
    # by username in any case, or by id (which both sites have here)
    assert creators_of(wanted=["Second_Creator"]) == [("onlyfans", SECOND)]
    assert creators_of(wanted=["123"]) == [("onlyfans", 123), ("fansly", SAME_ID)]
    assert creators_of(["onlyfans"], wanted=["123"]) == [("onlyfans", 123)]
    assert creators_of(wanted=["creator", SAME_ID_NAME]) == [("onlyfans", 123), ("fansly", SAME_ID)]
    # a username is its own site's: the Fansly creator numbered 123 isn't "creator"
    assert creators_of(wanted=["creator"]) == [("onlyfans", 123)]
    assert creators_of(wanted=[SAME_ID_NAME]) == [("fansly", SAME_ID)]


def test_a_creator_is_found_by_an_id_or_by_any_username_it_has_had(server):
    """So one request can find several: an id is looked for on both sites,
    and a username may be another creator's id."""
    server.insert("onlyfans", "models", ["model_id"], [(5,), (6,), (130,)])
    server.insert("fansly", "models", ["model_id"], [(130,)])
    server.insert(
        "onlyfans", "profiles", ["user_id", "username"],
        [(5, "Former_Name"), (5, "Current_Name"), (6, "130"), (130, "plain")],
    )

    assert creators_of(wanted=["current_name"]) == [("onlyfans", 5)]
    assert creators_of(wanted=["CURRENT_NAME"]) == [("onlyfans", 5)]
    assert creators_of(wanted=["former_name"]) == [("onlyfans", 5)]
    assert creators_of(wanted=["130"]) == [("onlyfans", 130), ("onlyfans", 6), ("fansly", 130)]
    assert creators_of(["onlyfans"], wanted=["plain", "6"]) == [("onlyfans", 130), ("onlyfans", 6)]


def test_creators_come_in_the_order_a_data_folder_gives_them(server):
    for creator in (9, 100, 20):
        server.insert("onlyfans", "models", ["model_id"], [(creator,)])
    # known only by its media: no scan listed it
    server.insert("onlyfans", "medias", ["media_id", "post_id", "model_id"], [(1, 1, 1000), (2, 1, 1000)])

    assert creators_of() == [("onlyfans", 100), ("onlyfans", 1000), ("onlyfans", 20), ("onlyfans", 9)]


def test_a_creator_without_a_saved_username_is_named_by_its_id(server):
    """As a file's creator is named by its folder, which the default layout
    names after the id."""
    server.insert(
        "onlyfans", "medias",
        ["media_id", "post_id", "directory", "filename", "media_type", "downloaded", "model_id"],
        [(1, 2, "folder", "one.jpg", "Images", True, 77)],
    )
    stash = Recording([("image", os.path.join("folder", "one.jpg"))])

    report = from_postgres(URL, stash, apply=True)

    assert report["models"][0]["performer"] == "77"
    # no page of its own to link to: its username isn't known
    assert ("performer", {"name": "77"}) in stash.created


def test_a_file_is_one_performer_and_postgresql_has_one_for_each_creator(tmp_path, server):
    """A file is taken to be one creator's, whatever its rows say (Merge
    Databases makes files with two creators' rows). PostgreSQL tells the
    creators apart. One with nothing but a username saved has no files in a
    file, and isn't a creator to PostgreSQL."""
    data = tmp_path / ".data"
    db = write_file(
        data / "5" / "user_data.db", 5, "the_first",
        medias=[(1, 1, "folder", "first.jpg", "Timeline", "Images", 1, 0, None, None)],
    )
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO profiles (user_id, username) VALUES (6, 'the_second')")
        conn.execute(
            "INSERT INTO medias (media_id, post_id, directory, filename, media_type, downloaded, model_id)"
            " VALUES (2, 2, 'folder', 'second.jpg', 'Images', 1, 6)"
        )
    write_file(data / "7" / "user_data.db", 7, "only_a_name")
    server.bring_in(data, tmp_path / "staging")

    from_files = sync([data], Recording())
    from_database = from_postgres(URL, Recording())

    assert [(m["performer"], m["files"]) for m in from_files["models"]] == [("the_second", 2), ("only_a_name", 0)]
    assert [(m["performer"], m["files"]) for m in from_database["models"]] == [("the_first", 1), ("the_second", 1)]


def test_a_creator_nobody_has_is_said(more_creators, server, tmp_path, monkeypatch, capsys):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")

    with pytest.raises(creator_rows.NotFound) as raised:
        creators_of(["fansly"], wanted=[SECOND_NAME, "Nobody"])
    assert str(raised.value) == f"PostgreSQL has no creator named nobody, {SECOND_NAME} (looked in: fansly)"
    assert server.events[-1] == ("close",)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--creator", "nobody", "--url", "http://127.0.0.1:9/graphql")
    assert (code, out) == (1, "")
    assert err == "error: PostgreSQL has no creator named nobody (looked in: onlyfans, fansly)\n"


def test_a_database_without_the_scrapers_tables_has_no_creators(server, stash_server, monkeypatch, capsys):
    _, url = stash_server
    assert creators_of() == []

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--url", url)

    assert (code, err) == (0, "")
    assert json.loads(out) == {"apply": False, "models": [], "totals": {}}


# --- the command ---


def test_cli_reads_postgresql_when_told_and_gives_the_report_the_files_give(
    everything, server, stash_server, tmp_path, monkeypatch, capsys
):
    data, in_stash = everything
    server.bring_in(data, tmp_path / "staging")
    stash, url = stash_server
    for kind, path in in_stash:
        stash.add(kind, path)
    assert stash_sync.main([str(data), "--url", url]) == 0
    from_files = json.loads(capsys.readouterr().out)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--url", url)

    # nothing but the report, and no word about files: it didn't read any
    assert (code, err) == (0, "")
    assert without_sources(json.loads(out)) == without_sources(from_files)
    assert from_files["totals"]["to_update"] >= 12
    assert [event[0] for event in server.events].count("connect") == 1

    # what it writes is what the files would have had written: they find
    # nothing left to do
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--url", url, "--apply")
    assert (code, err) == (0, "")
    assert json.loads(out)["totals"]["updated"] == from_files["totals"]["to_update"]
    assert stash_sync.main([str(data), "--url", url, "--apply"]) == 0
    again = json.loads(capsys.readouterr().out)["totals"]
    assert again["up_to_date"] == from_files["totals"]["to_update"]
    assert not {"updated", "galleries_created", "galleries_updated"} & set(again)


def test_cli_picks_a_site_and_creators(everything, server, stash_server, tmp_path, monkeypatch, capsys):
    data, _ = everything
    server.bring_in(data, tmp_path / "staging")
    _, url = stash_server

    def performers(*args):
        code, out, err = cli(monkeypatch, capsys, "--postgres", "--url", url, *args)
        assert (code, err) == (0, "")
        return [model["performer"] for model in json.loads(out)["models"]]

    assert performers() == PERFORMERS
    assert performers("--site", "fansly") == ["samplecreator2", SAME_ID_NAME]
    assert performers("--creator", "OFCREATOR", "--creator", str(SECOND)) == [OF_USER, SECOND_NAME]
    assert performers("--site", "onlyfans", "--creator", "123") == ["creator"]


def test_the_database_is_read_once_and_closed_before_stash_is_asked(everything, server, tmp_path, monkeypatch, capsys):
    data, in_stash = everything
    server.bring_in(data, tmp_path / "staging")
    stash = Recording(in_stash)
    events = server.events

    class Client:
        def __init__(self, url, api_key):
            pass

        def call(self, query, variables=None):
            events.append(("stash",))
            return stash.call(query, variables)

    monkeypatch.setattr(stash_sync, "StashClient", Client)

    code, _, err = cli(monkeypatch, capsys, "--postgres", "--apply")

    assert (code, err) == (0, "")
    kinds = [event[0] for event in events]
    # one connection, to the address in the environment
    assert [event for event in events if event[0] == "connect"] == [("connect", URL)]
    assert kinds.count("close") == 1
    assert kinds.index("close") < kinds.index("stash")
    assert set(kinds[kinds.index("close") + 1:]) == {"stash"}
    # it only reads
    assert all(event[1].startswith("SELECT ") for event in events if event[0] == "query")


def test_only_the_commands_own_environment_is_asked(more_creators, server, stash_server, tmp_path, monkeypatch, capsys):
    """Not the scraper's settings: they bring the scraper's environment and
    errors into the command."""
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    _, url = stash_server

    def asked(*args, **kwargs):
        raise AssertionError("the scraper's settings were asked")

    monkeypatch.setattr(postgres.of_env, "getattr", asked)
    monkeypatch.setattr(postgres, "url", asked)
    monkeypatch.setattr(postgres, "enabled", asked)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--url", url)

    assert (code, err) == (0, "")
    assert len(json.loads(out)["models"]) == 2


@pytest.mark.parametrize(
    "args, said",
    [
        (["--postgres", "some/.data"], "give user_data.db files or --postgres, not both"),
        (["--site", "fansly", "some/.data"], "--site and --creator go with --postgres"),
        (["--creator", "a_creator", "some/.data"], "--site and --creator go with --postgres"),
        ([], "the following arguments are required: paths, or --postgres"),
        (["--postgres", "--site", "another"], "invalid choice: 'another'"),
        (["--postgres", "--creator", ""], "--creator needs a username or an id, and was given none"),
        (["--postgres", "--creator", "a_creator", "--creator", "  "], "--creator needs a username or an id"),
    ],
)
def test_cli_refuses_what_it_cant_make_sense_of(monkeypatch, capsys, args, said):
    monkeypatch.setattr(postgres, "Reader", lambda url: pytest.fail("nothing to connect for"))

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
        stash_sync.main(["--postgres"])

    said = capsys.readouterr()
    assert (stopped.value.code, said.out) == (2, "")
    assert "--postgres needs OFSC_DATABASE_URL set in the environment this is run in" in said.err
    assert "POSTGRESQL.md" in said.err


def test_cli_given_files_reads_the_files_and_says_so_while_postgresql_is_on(
    library, stash_server, monkeypatch, capsys
):
    db, media_dir = library
    stash, url = stash_server
    stash.add("scene", str(media_dir / "post.mp4"))
    monkeypatch.setattr(postgres, "Reader", lambda url: pytest.fail("PostgreSQL wasn't asked for"))

    code, out, err = cli(monkeypatch, capsys, str(db), "--url", url)

    assert code == 0
    assert err == (
        "warning: PostgreSQL is on (OFSC_DATABASE_URL is set), but stash_sync works on the"
        " user_data.db files it was given, not PostgreSQL. They hold nothing scraped since"
        " PostgreSQL was turned on. To read PostgreSQL, give --postgres in place of the files."
        " See POSTGRESQL.md.\n"
    )
    assert json.loads(out)["models"][0]["database"] == str(db)


# --- what goes wrong ---


def test_a_read_that_fails_stops_the_run_before_stash_is_asked(more_creators, server, tmp_path, monkeypatch, capsys):
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    server.fails_on = "medias"
    monkeypatch.setattr(stash_sync.StashClient, "call", lambda *a, **k: pytest.fail("Stash was asked"))

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--apply")

    assert (code, out) == (1, "")
    assert err == (
        "error: Can't read the PostgreSQL database at db.example:5433/library."
        " (server closed the connection unexpectedly)\n"
    )
    assert server.events[-1] == ("close",)


def test_a_login_that_may_not_read_a_sites_tables_is_told_so(
    more_creators, library, server, stash_server, tmp_path, monkeypatch, capsys
):
    """Not given an empty report: to such a login the tables look as if
    they weren't there."""
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    _, url = stash_server
    server.forbid("fansly")

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--apply", "--url", url)

    assert (code, out) == (1, "")
    assert err.startswith(
        "error: Can't read the PostgreSQL database at db.example:5433/library:"
        " the user isn't allowed to read the fansly tables ("
    )
    assert ", medias, " in err and err.endswith(").\n") and err.count("\n") == 1
    assert server.events[-1] == ("close",)
    # the site it may read is read
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--site", "onlyfans", "--url", url)
    assert (code, err) == (0, "")
    assert [model["performer"] for model in json.loads(out)["models"]] == ["creator", SECOND_NAME]

    # one table is enough: without it the creators would seem to have no files
    server.forbid("onlyfans", ["medias"])
    code, out, err = cli(monkeypatch, capsys, "--postgres", "--site", "onlyfans", "--url", url)
    assert (code, out) == (1, "")
    assert err == (
        "error: Can't read the PostgreSQL database at db.example:5433/library:"
        " the user isn't allowed to read the onlyfans tables (medias).\n"
    )


def test_a_read_the_server_ends_for_taking_too_long_is_one_sentence(monkeypatch, capsys):
    psycopg = pytest.importorskip("psycopg")
    ended = psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: Connection(fails=ended))
    monkeypatch.setattr(stash_sync.StashClient, "call", lambda *a, **k: pytest.fail("Stash was asked"))

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--apply")

    assert (code, out) == (1, "")
    assert err == (
        "error: Can't read the PostgreSQL database at db.example:5433/library."
        " (canceling statement due to statement timeout)\n"
    )


def test_cli_never_repeats_the_address_or_its_password(monkeypatch, capsys):
    # the password is found as the driver reads the address
    pytest.importorskip("psycopg")

    def refuses(url):
        raise postgres.PostgresUnavailable(f"could not connect to {url} (password s3cret-word)")

    monkeypatch.setattr(postgres, "Reader", refuses)

    code, out, err = cli(monkeypatch, capsys, "--postgres")

    assert (code, out) == (1, "")
    assert err == "error: could not connect to {hidden} (password {hidden})\n"


def test_a_missing_driver_is_one_sentence(monkeypatch, capsys):
    real_import = builtins.__import__

    def no_driver(name, *args, **kwargs):
        if name.split(".")[0] in ("psycopg", "psycopg_pool"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_driver)

    code, out, err = cli(monkeypatch, capsys, "--postgres")

    assert (code, out) == (1, "")
    assert err.startswith("error: OFSC_DATABASE_URL is set, but the PostgreSQL driver isn't installed.")
    assert "[postgres]" in err and err.count("\n") == 1


def test_a_server_that_isnt_there_is_one_sentence(monkeypatch, capsys):
    pytest.importorskip("psycopg")
    monkeypatch.setattr(stash_sync.StashClient, "call", lambda *a, **k: pytest.fail("Stash was asked"))
    # Windows waits the whole time for a port nothing listens on
    monkeypatch.setattr(postgres, "CONNECT_TIMEOUT", 2)

    code, out, err = cli(monkeypatch, capsys, "--postgres", "--apply", url=NOWHERE)

    assert (code, out) == (1, "")
    assert err.startswith(
        "error: Can't use the PostgreSQL database at 127.0.0.1:9/library: the server can't be reached. ("
    )
    assert err.count("\n") == 1
    assert "s3cret-word" not in err and "scraper" not in err


def test_an_address_the_driver_cant_read_is_said_without_quoting_it(monkeypatch, capsys):
    pytest.importorskip("psycopg")

    code, out, err = cli(monkeypatch, capsys, "--postgres", url="postgres//scraper:s3cret-word@db.example/library")

    assert (code, out) == (1, "")
    assert err == (
        "error: OFSC_DATABASE_URL isn't an address PostgreSQL can read. It should look like"
        " postgresql://user:password@host:5432/database.\n"
    )


# --- the connection (postgres.Reader), with the driver's connect stood in for ---


class Connection:
    """What Reader does to its connection, in order."""

    def __init__(self, fails=None):
        self.did = []
        self.fails = fails

    def __setattr__(self, name, value):
        if name in ("read_only", "isolation_level"):
            self.did.append((name, value))
        object.__setattr__(self, name, value)

    def execute(self, query):
        self.did.append(query)

    def commit(self):
        self.did.append("commit")

    def cursor(self):
        raise self.fails

    def close(self):
        self.did.append("close")


def test_the_connection_is_read_only_and_sees_the_database_at_one_moment(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    made = {}

    def connect(url, **kwargs):
        made.update(url=url, kwargs=kwargs, conn=Connection())
        return made["conn"]

    monkeypatch.setattr(psycopg, "connect", connect)

    reader = postgres.Reader(URL)

    assert made["url"] == URL
    # values come out as the engine's do
    assert made["kwargs"]["context"] is postgres._adapters()
    assert made["kwargs"]["cursor_factory"] is postgres._cursor_class()
    assert made["kwargs"]["row_factory"] is postgres.row_factory
    assert made["kwargs"]["connect_timeout"] == postgres.CONNECT_TIMEOUT
    # a server that is gone is noticed, and no statement is kept on the server
    assert {k: v for k, v in made["kwargs"].items() if k.startswith("keepalives")} == {
        "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3,
    }
    assert "prepare_threshold" in made["kwargs"] and made["kwargs"]["prepare_threshold"] is None
    assert made["conn"].did == [
        "SET TIME ZONE 'UTC'",
        "SET DateStyle TO 'ISO, YMD'",
        # a read that waits or runs on is ended by the server
        "SET lock_timeout = 30000",
        "SET statement_timeout = 300000",
        "commit",
        ("read_only", True),
        ("isolation_level", psycopg.IsolationLevel.REPEATABLE_READ),
    ]
    reader.close()
    reader.close()
    assert made["conn"].did[-2:] == [("isolation_level", psycopg.IsolationLevel.REPEATABLE_READ), "close"]


def test_a_read_the_server_refuses_is_one_sentence_without_the_login(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    lost = psycopg.OperationalError(f"connection to\n{URL} was lost\n(password s3cret-word)")
    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: Connection(fails=lost))
    reader = postgres.Reader(URL)

    with pytest.raises(postgres.PostgresUnavailable) as raised:
        reader.rows("SELECT 1")

    assert str(raised.value) == (
        "Can't read the PostgreSQL database at db.example:5433/library."
        " (connection to {hidden} was lost (password {hidden}))"
    )


def test_a_connection_that_fails_part_way_is_closed(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    made = []

    class Refuses(Connection):
        def commit(self):
            raise psycopg.OperationalError("server closed the connection unexpectedly")

    monkeypatch.setattr(psycopg, "connect", lambda url, **kwargs: made.append(Refuses()) or made[0])

    with pytest.raises(postgres.PostgresUnavailable) as raised:
        postgres.Reader(URL)

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


def test_given_files_the_driver_isnt_loaded(tmp_path):
    result = run_tool(
        "import sys\n"
        "import ofscraper.commands.stash_sync as stash_sync\n"
        f"code = stash_sync.main([{str(tmp_path)!r}, '--url', 'http://127.0.0.1:9/graphql'])\n"
        f"{LOADED}\n"
        "sys.exit(code)",
        **{postgres.URL_KEY: URL},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "[]"
    assert result.stderr.startswith("warning: PostgreSQL is on")


def test_reading_postgresql_doesnt_load_the_scraper():
    """Nor does a setting the scraper would stop on stop it."""
    pytest.importorskip("psycopg")
    result = run_tool(
        "import sys\n"
        "import ofscraper.commands.stash_sync as stash_sync\n"
        # Windows waits the whole time for a port nothing listens on
        "stash_sync.postgres.CONNECT_TIMEOUT = 2\n"
        "code = stash_sync.main(['--postgres'])\n"
        f"{LOADED}\n"
        "sys.exit(code)",
        OFSC_DOWNLOAD_SEM_DEFAULT="many",
        **{postgres.URL_KEY: NOWHERE},
    )

    assert result.returncode == 1, result.stderr
    # the driver, and nothing of the scraper's
    loaded = {name.split(".")[0] for name in ast.literal_eval(result.stdout)}
    assert loaded == {"psycopg", "psycopg_pool"}
    assert result.stderr.startswith("error: Can't use the PostgreSQL database at 127.0.0.1:9/library")
    assert "Traceback" not in result.stderr and "s3cret-word" not in result.stderr
