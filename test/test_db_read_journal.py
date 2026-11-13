"""`ofscraper db` only reads a database (#373).

The shared wrapper set WAL mode and took the write lock for every operation,
so just reading a database switched it from rollback journal mode to WAL,
and a read-only database file couldn't be read at all. The db command's
readers now open the file read-only; writes keep WAL.
"""

import asyncio
import contextlib
import hashlib
import os
import pathlib
import sqlite3
import stat
from pathlib import PurePosixPath, PureWindowsPath
from types import SimpleNamespace

import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.db as db_command
import ofscraper.db.operations_.media as media_ops
import ofscraper.db.operations_.wrapper as wrapper

ALL_AREAS = [
    "Timeline",
    "Pinned",
    "Archived",
    "Messages",
    "Streams",
    "Highlights",
    "Stories",
]
READERS = [
    "get_all_medias",
    "get_timeline_media",
    "get_pinned_media",
    "get_archived_media",
    "get_messages_media",
    "get_streams_media",
    "get_highlights_media",
    "get_stories_media",
    "get_permanent_skip_media_ids",
]


def make_db(path):
    """A real database in rollback (delete) journal mode, with two rows."""
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(media_ops.mediaCreate)
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " created_at, posted_at, model_id, skip_permanent)"
            " VALUES (?, ?, ?, 'Images', '2024-01-01', '2024-01-02', 5, ?)",
            [(1, 100, "timeline", 1), (2, 101, "messages", None)],
        )
        conn.commit()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def journal_mode(path):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return conn.execute("PRAGMA journal_mode").fetchone()[0]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_command(monkeypatch, path_for, areas=ALL_AREAS, unmark=False):
    """Settings for `ofscraper db`, and its readers reading
    path_for(model_id); with path_for=None they use the usual path."""
    args = SimpleNamespace(
        download_area=areas,
        downloaded=None,
        protected=False,
        normal=False,
        unlocked=None,
        preview=None,
        post_id=None,
        media_id=None,
        unmark_permanent_skips=unmark,
    )
    options = SimpleNamespace(
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
        export=None,
        anon=False,
    )
    monkeypatch.setattr(db_command.settings, "get_args", lambda: args)
    monkeypatch.setattr(db_command.settings, "get_settings", lambda: options)
    if path_for is None:
        return
    for name in READERS:
        reader = getattr(db_command, name)
        monkeypatch.setattr(
            db_command,
            name,
            lambda reader=reader, **kwargs: reader(
                **kwargs, db_path=path_for(kwargs["model_id"])
            ),
        )


@pytest.fixture
def run_db(monkeypatch):
    """Run `ofscraper db`'s reads on one database; returns its rows."""

    def run(path, areas=ALL_AREAS, unmark=False):
        patch_command(monkeypatch, lambda model_id: path, areas, unmark)
        manager = db_command.DBManager("a creator", 5)
        # the command's run() keeps the current loop open; close it after
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            manager.get_wanted_media()
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return [row["media_id"] for row in manager.media]

    return run


@pytest.fixture
def connections(monkeypatch):
    """Counts the wrapper's connections: one per read means no retries."""
    opened = []
    real = sqlite3.connect

    def connect(*args, **kwargs):
        opened.append(args[0])
        return real(*args, **kwargs)

    monkeypatch.setattr(wrapper.sqlite3, "connect", connect)
    return opened


@pytest.mark.parametrize(
    "areas,unmark",
    [(ALL_AREAS, False), (["Timeline", "Messages"], False), (ALL_AREAS, True)],
    ids=["all areas", "some areas", "unmark filter"],
)
def test_db_leaves_rollback_database_unchanged(tmp_path, run_db, areas, unmark):
    # Given a database in rollback journal mode
    path = tmp_path / "user_data.db"
    make_db(path)
    before = digest(path)

    # When ofscraper db only reads it
    rows = run_db(path, areas, unmark)

    # Then the rows are shown
    assert rows == ([1] if unmark else [1, 2])
    # and its journal mode and bytes are unchanged, with no WAL files beside it
    assert path.read_bytes()[18:20] == b"\x01\x01"
    assert digest(path) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["user_data.db"]
    assert journal_mode(path) == "delete"


@pytest.mark.parametrize("mode", ["delete", "wal"])
def test_db_reads_read_only_file(tmp_path, run_db, connections, mode):
    # Given a read-only database file
    path = tmp_path / "user_data.db"
    make_db(path)
    if mode == "wal":
        with contextlib.closing(sqlite3.connect(path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
    before = digest(path)
    os.chmod(path, stat.S_IREAD)
    connections.clear()
    try:
        # When ofscraper db reads it
        rows = run_db(path)
        assert digest(path) == before
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)

    # Then the rows are shown, with no error and no retries
    assert rows == [1, 2]
    assert len(connections) == 1


def test_sync_wrapper_reads_read_only_file(tmp_path, connections):
    # the synchronous wrapper takes read_only=True the same way
    path = tmp_path / "user_data.db"
    make_db(path)
    before = digest(path)
    os.chmod(path, stat.S_IREAD)
    connections.clear()
    try:
        ids = media_ops.get_media_post_ids(model_id=5, db_path=path, read_only=True)
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    assert sorted(ids) == [(1, 100), (2, 101)]
    assert len(connections) == 1
    assert digest(path) == before
    assert journal_mode(path) == "delete"


def make_empty(path):
    """The empty file older `ofscraper db` runs left for a new creator."""
    path.touch()


def make_without_medias(path):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE other (x)")
        conn.commit()


@pytest.fixture
def run_command(tmp_path, monkeypatch, caplog):
    """Run the whole `ofscraper db` command over creators whose databases
    are tmp_path/<id>.db. Returns the exported rows and the files the
    wrapper tried to open, one entry per try."""

    def by_id(model_id):
        return tmp_path / f"{model_id}.db"

    def run(creators, areas=ALL_AREAS, path_for=by_id):
        patch_command(monkeypatch, path_for, areas)
        monkeypatch.setattr(
            db_command,
            "manager",
            SimpleNamespace(
                Manager=SimpleNamespace(
                    current_model_manager=SimpleNamespace(
                        sync_models=lambda **kwargs: None, all_subs=creators
                    )
                )
            ),
        )
        monkeypatch.setattr(db_command.actions, "select_areas", lambda: None)
        monkeypatch.setattr(db_command.time, "sleep", lambda seconds: None)
        # the table's printing sets up log handlers; the rows are checked
        monkeypatch.setattr(
            db_command.DBManager, "print_dictionary_table", lambda self: None
        )
        exported = []
        monkeypatch.setattr(db_command, "write_csv", exported.extend)
        attempts = []
        real_connect = wrapper._connect

        def connect(database_path, read_only, **kwargs):
            attempts.append(database_path.name)
            return real_connect(database_path, read_only, **kwargs)

        monkeypatch.setattr(wrapper, "_connect", connect)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with caplog.at_level("WARNING", logger="shared"):
                db_command.db()
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return exported, attempts

    return run


@pytest.mark.parametrize(
    "areas", [ALL_AREAS, ["Timeline", "Messages"]], ids=["all areas", "some areas"]
)
@pytest.mark.parametrize(
    "make_new",
    [None, make_empty, make_without_medias],
    ids=["no file", "empty file", "no medias table"],
)
def test_db_skips_creator_without_database(
    tmp_path, caplog, run_command, areas, make_new
):
    # Given two creators, one with no database yet: no file, the empty file
    # an older run left, or a file without the medias table
    make_db(tmp_path / "5.db")
    missing = tmp_path / "6.db"
    if make_new:
        make_new(missing)
        before = digest(missing)

    # When ofscraper db runs
    exported, attempts = run_command(
        [
            SimpleNamespace(name="new creator", id=6),
            SimpleNamespace(name="a creator", id=5),
        ],
        areas,
    )

    # Then a plain message says the creator has no database yet, and the
    # command goes on to the next creator
    assert "new creator has no database yet, skipping" in caplog.text
    assert "Traceback" not in caplog.text
    assert sorted(row["media_id"] for row in exported) == [1, 2]
    # with one attempt only (no retries), and no file created or changed
    assert attempts.count("6.db") == 1
    if make_new:
        assert digest(missing) == before
        assert sorted(p.name for p in tmp_path.iterdir()) == ["5.db", "6.db"]
    else:
        assert not missing.exists()


@pytest.fixture
def usual_paths(monkeypatch, tmp_path):
    """The real database path helper, with its config, profile and login
    pointed at tmp_path: a creator's database is
    tmp_path/cfg/main_profile/.data/<username>/user_data.db."""
    # the app's logger gains .trace at startup; tests don't run that setup
    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(
        placeholder.profile_data, "get_active_profile", lambda: "main_profile"
    )
    monkeypatch.setattr(
        placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg"
    )
    monkeypatch.setattr(
        placeholder.common_paths,
        "get_save_location",
        lambda *a, **k: str(tmp_path / "data"),
    )
    monkeypatch.setattr(
        placeholder.data,
        "get_metadata",
        lambda *a, **k: "{configpath}/{profile}/.data/{model_username}",
    )
    return tmp_path / "cfg" / "main_profile" / ".data"


def test_db_makes_no_folder_for_creator_without_database(
    tmp_path, caplog, run_command, usual_paths
):
    # Given two creators at their usual paths, one with no database yet
    folder = usual_paths / "a creator"
    folder.mkdir(parents=True)
    make_db(folder / "user_data.db")
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    # When ofscraper db runs, working out each path itself
    exported, _ = run_command(
        [
            SimpleNamespace(name="new creator", id=6),
            SimpleNamespace(name="a creator", id=5),
        ],
        path_for=None,
    )

    # Then the new creator is skipped and gets no folder and no file, and
    # nothing else on disk changes
    assert "new creator has no database yet, skipping" in caplog.text
    assert sorted(row["media_id"] for row in exported) == [1, 2]
    assert not (usual_paths / "new creator").exists()
    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before

    # and a write (as a scrape makes) still makes the folder and database
    asyncio.run(media_ops.create_media_table(model_id=6, username="new creator"))
    assert journal_mode(usual_paths / "new creator" / "user_data.db") == "wal"


def test_db_skips_unreadable_databases(tmp_path, caplog, monkeypatch, run_command):
    # Given three creators: one whose database SQLite can't open, one whose
    # file isn't a database, and one that's fine
    make_db(tmp_path / "5.db")
    make_db(tmp_path / "7.db")
    (tmp_path / "8.db").write_bytes(b"not a database, " * 256)
    real_connect = sqlite3.connect

    def connect(target, *args, **kwargs):
        if "7.db" in str(target):
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr(wrapper.sqlite3, "connect", connect)

    # When ofscraper db runs
    exported, attempts = run_command(
        [
            SimpleNamespace(name="locked out creator", id=7),
            SimpleNamespace(name="broken creator", id=8),
            SimpleNamespace(name="a creator", id=5),
        ]
    )

    # Then each bad one is named, with its path and the reason, and skipped
    # after one try, and the other creator is still exported
    assert (
        f"locked out creator: can't read the database at {tmp_path / '7.db'}"
        " (unable to open database file), skipping"
    ) in caplog.text
    assert (
        f"broken creator: can't read the database at {tmp_path / '8.db'}"
        " (file is not a database), skipping"
    ) in caplog.text
    assert attempts.count("7.db") == 1
    assert attempts.count("8.db") == 1
    assert sorted(row["media_id"] for row in exported) == [1, 2]


@pytest.mark.parametrize("read_only", [True, False], ids=["read", "write"])
def test_open_failure_is_not_retried(tmp_path, monkeypatch, read_only):
    # an existing file SQLite can't open: a retry can't fix that, on the
    # read path or the write path, async or sync
    path = tmp_path / "user_data.db"
    make_db(path)
    attempts = []

    def connect(*args, **kwargs):
        attempts.append(args[0])
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(wrapper.sqlite3, "connect", connect)
    if read_only:
        calls = [
            lambda: asyncio.run(
                media_ops.get_all_medias(db_path=path, read_only=True)
            ),
            lambda: media_ops.get_media_post_ids(db_path=path, read_only=True),
        ]
    else:
        calls = [
            lambda: asyncio.run(media_ops.create_media_table(db_path=path)),
            lambda: media_ops.batch_set_media_downloaded(
                [], model_id=5, db_path=path
            ),
        ]
    for call in calls:
        with pytest.raises(wrapper.DatabaseUnreadable) as raised:
            call()
        assert raised.value.database_path == path.resolve()
    assert len(attempts) == 2


def test_not_a_database_is_not_retried_on_write(tmp_path, monkeypatch):
    path = tmp_path / "user_data.db"
    path.write_bytes(b"not a database, " * 256)
    attempts = []
    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        attempts.append(args[0])
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(wrapper.sqlite3, "connect", connect)
    with pytest.raises(sqlite3.DatabaseError, match="file is not a database"):
        asyncio.run(media_ops.create_media_table(db_path=path))
    with pytest.raises(sqlite3.DatabaseError, match="file is not a database"):
        media_ops.batch_set_media_downloaded([], model_id=5, db_path=path)
    assert len(attempts) == 2


@pytest.mark.parametrize("read_only", [True, False], ids=["read", "write"])
def test_busy_database_is_still_retried(tmp_path, monkeypatch, read_only):
    # a locked database can free up, so it's tried again
    path = tmp_path / "user_data.db"
    make_db(path)
    attempts = []
    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        attempts.append(args[0])
        if len(attempts) == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(wrapper.sqlite3, "connect", connect)
    if read_only:
        rows = asyncio.run(
            media_ops.get_all_medias(model_id=5, db_path=path, read_only=True)
        )
        assert len(rows) == 2
    else:
        asyncio.run(media_ops.create_media_table(db_path=path))
    assert len(attempts) == 2


@pytest.mark.parametrize(
    "path,uri",
    [
        (
            PureWindowsPath(r"C:\data dir\#1 100%\é.db"),
            "file:///C:/data%20dir/%231%20100%25/%C3%A9.db?mode=ro",
        ),
        (
            PureWindowsPath(r"\\server\share\a b\user_data.db"),
            "file:////server/share/a%20b/user_data.db?mode=ro",
        ),
        (
            PurePosixPath("/home/a b/#1 100%/é.db"),
            "file:///home/a%20b/%231%20100%25/%C3%A9.db?mode=ro",
        ),
    ],
    ids=["drive", "unc", "posix"],
)
def test_read_only_uri(path, uri):
    assert wrapper._read_only_uri(path) == uri


def test_read_only_reads_unusual_folder_name(tmp_path):
    folder = tmp_path / "a b #1 100% é"
    folder.mkdir()
    path = folder / "user_data.db"
    make_db(path)
    rows = asyncio.run(
        media_ops.get_all_medias(model_id=5, db_path=path, read_only=True)
    )
    assert sorted(row["media_id"] for row in rows) == [1, 2]


def test_read_only_reads_unc_path(tmp_path):
    # a database on a network share, reached through the admin share
    if os.name != "nt" or not tmp_path.drive.endswith(":"):
        pytest.skip("UNC paths are Windows paths")
    unc = pathlib.Path(
        rf"\\localhost\{tmp_path.drive[0]}$" + str(tmp_path)[2:]
    ) / "user_data.db"
    try:
        reachable = unc.parent.is_dir()
    except OSError:
        reachable = False
    if not reachable:
        pytest.skip("the localhost admin share isn't reachable")
    make_db(tmp_path / "user_data.db")
    before = digest(tmp_path / "user_data.db")
    rows = asyncio.run(
        media_ops.get_all_medias(model_id=5, db_path=unc, read_only=True)
    )
    assert sorted(row["media_id"] for row in rows) == [1, 2]
    assert digest(tmp_path / "user_data.db") == before


def test_write_still_uses_wal(tmp_path, run_db):
    # Given a rollback database that ofscraper db has read
    path = tmp_path / "user_data.db"
    make_db(path)
    run_db(path)

    # When something writes to it (a table check as a scrape makes, and
    # the db command's own un-marking)
    asyncio.run(media_ops.create_media_table(db_path=path))
    changed = asyncio.run(
        media_ops.unmark_permanent_skips([1], model_id=5, db_path=path)
    )

    # Then the database uses WAL, and the write is kept
    assert changed == 1
    assert journal_mode(path) == "wal"
    with contextlib.closing(sqlite3.connect(path)) as conn:
        assert conn.execute(
            "SELECT skip_permanent FROM medias WHERE media_id = 1"
        ).fetchone() == (None,)
