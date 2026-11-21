"""The database wrapper asks one object, the engine, for everything that is
SQLite's own (#608): opening and closing, which errors a retry can fix,
whether a creator has a database, and what tables and columns exist. Another
engine can then stand in by providing the same methods.
"""

import asyncio
import contextlib
import pathlib
import re
import sqlite3

import pytest
import tenacity

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.db.operations as operations
import ofscraper.db.operations_.profile as profile
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.utils.columns as db_columns

OPERATIONS = pathlib.Path(operations.__file__).parent / "operations_"
TABLE_MODULES = sorted(
    path for path in OPERATIONS.glob("*.py") if path.name != "wrapper.py"
)


class OtherEngineError(Exception):
    """An error only the stand-in engine knows."""


class Recorder:
    """A stand-in engine: SQLite's, with every call written down."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        real = getattr(wrapper.SQLITE, name)
        if not callable(real):
            return real

        def call(*args, **kwargs):
            self.calls.append(name)
            return real(*args, **kwargs)

        return call

    def retryable(self, error):
        return isinstance(error, OtherEngineError)

    def busy(self, error):
        return False


@pytest.fixture
def engine(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(wrapper, "backend_for", lambda kwargs: recorder)
    monkeypatch.setattr(wrapper, "_BACKENDS", [wrapper.SQLITE, recorder])
    return recorder


def call(wrap, func, **kwargs):
    wrapped = wrap(func)
    if wrap is wrapper.operation_wrapper_async:
        return asyncio.run(wrapped(**kwargs))
    return wrapped(**kwargs)


WRAPPERS = pytest.mark.parametrize(
    "wrap",
    [wrapper.operation_wrapper, wrapper.operation_wrapper_async],
    ids=["sync", "async"],
)


def test_the_table_modules_do_not_name_sqlite3():
    # they catch wrapper.DB_ERRORS and ask the engine about tables
    named = [
        path.name
        for path in TABLE_MODULES
        if re.search(r"\bsqlite3\b|sqlite_master", path.read_text(encoding="utf-8"))
    ]
    assert len(TABLE_MODULES) >= 8
    assert named == []


@WRAPPERS
def test_an_operation_goes_through_the_engine(tmp_path, wrap, engine):
    def work(conn=None, **kwargs):
        engine.calls.append("work")
        return conn.execute("SELECT 5").fetchone()[0]

    assert call(wrap, work, db_path=tmp_path / "a.db") == 5
    assert engine.calls == ["where", "connect", "work", "close"]


@WRAPPERS
def test_the_engine_names_the_error_and_closes(tmp_path, wrap, engine):
    def work(conn=None, **kwargs):
        raise ValueError("no")

    with pytest.raises(ValueError):
        call(wrap, work, db_path=tmp_path / "a.db")
    assert engine.calls == ["where", "connect", "final_error", "close"]


@WRAPPERS
def test_an_error_another_engine_calls_retryable_is_retried(
    tmp_path, wrap, engine, monkeypatch
):
    monkeypatch.setattr(tenacity.nap.time, "sleep", lambda seconds: None)
    tries = []

    def work(conn=None, **kwargs):
        tries.append(1)
        if len(tries) < 3:
            raise OtherEngineError()
        return "done"

    assert call(wrap, work, db_path=tmp_path / "a.db") == "done"
    assert len(tries) == 3


def test_sqlite_does_not_claim_another_engines_error():
    assert wrapper.SQLITE.retryable(OtherEngineError()) is False
    assert wrapper.SQLITE.busy(OtherEngineError()) is False
    assert wrapper.SQLITE.retryable(sqlite3.OperationalError("database is locked"))


def test_the_engine_of_a_connection_or_cursor(tmp_path):
    with contextlib.closing(sqlite3.connect(tmp_path / "a.db")) as conn:
        assert wrapper.backend_of(conn) is wrapper.SQLITE
        with contextlib.closing(conn.cursor()) as cur:
            assert wrapper.backend_of(cur) is wrapper.SQLITE


def test_an_object_no_engine_owns_is_taken_for_sqlites():
    assert wrapper.backend_of(object()) is wrapper.SQLITE


def test_sqlite_answers_for_its_tables_and_columns(tmp_path):
    with contextlib.closing(sqlite3.connect(tmp_path / "a.db")) as conn:
        conn.execute("CREATE TABLE medias (id INTEGER, model_id INTEGER)")
        with contextlib.closing(conn.cursor()) as cur:
            assert wrapper.SQLITE.table_exists(cur, "medias") is True
            assert wrapper.SQLITE.table_exists(cur, "profiles") is False
            assert db_columns.table_columns(cur, "medias") == {"id", "model_id"}
            assert db_columns.table_columns(cur, "profiles") == set()


def test_the_columns_of_a_table_are_asked_of_the_engine(tmp_path, monkeypatch):
    asked = []

    def table_columns(cur, table):
        asked.append(table)
        return {"made", "up"}

    monkeypatch.setattr(wrapper.SQLITE, "table_columns", table_columns)

    with contextlib.closing(sqlite3.connect(tmp_path / "a.db")) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            assert db_columns.table_columns(cur, "medias") == {"made", "up"}
            # and so are the helpers built on it
            assert db_columns.creator_filter(cur, "medias", 5) == ("", [])
    assert asked == ["medias", "medias"]


@WRAPPERS
def test_a_connection_that_fails_to_start_is_closed_by_the_engine(
    tmp_path, wrap, monkeypatch
):
    # the wrapper never gets a connection that failed at BEGIN, so it can't
    # close it: the engine does
    opened = []
    real_connect = wrapper._connect

    class FailsAtBegin(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql.startswith("BEGIN"):
                raise ValueError("no")
            return super().execute(sql, *args)

    def connect(database_path, read_only, **kwargs):
        conn = real_connect(database_path, read_only, factory=FailsAtBegin, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(wrapper, "_connect", connect)

    with pytest.raises(ValueError):
        call(wrap, lambda conn=None, **kwargs: None, db_path=tmp_path / "a.db")

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")


def test_the_column_helpers_can_be_imported_before_anything_else():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import ofscraper.db.utils.columns"],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(operations.__file__).parents[2],
    )
    assert result.returncode == 0, result.stderr


def test_a_creator_has_a_database_once_its_file_is_there(tmp_path, monkeypatch):
    import ofscraper.classes.placeholder as placeholder

    path = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: path,
    )

    assert wrapper.database_exists(5, "a_creator") is False
    assert wrapper.database_exists(db_path=tmp_path / "other.db") is False
    path.touch()
    assert wrapper.database_exists(5, "a_creator") is True


def test_the_profile_checks_ask_the_engine(tmp_path, monkeypatch):
    import ofscraper.classes.placeholder as placeholder

    path = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: path,
    )
    asked = []
    real = wrapper.SQLITE.table_exists

    def table_exists(cur, table):
        asked.append(table)
        return real(cur, table)

    monkeypatch.setattr(wrapper.SQLITE, "table_exists", table_exists)

    async def go():
        before = await profile.check_profile_table_exists(model_id=5, username="a")
        await profile.create_profile_table(model_id=5, username="a")
        await profile.write_profile_table(model_id=5, username="a")
        return (
            before,
            await profile.check_profile_table_exists(model_id=5, username="a"),
            await profile.get_profile_info(model_id=5, username="a"),
            await profile.get_all_profiles(model_id=5, username="a"),
        )

    # the first check opens (and so creates) the file, which has no table yet
    assert asyncio.run(go()) == (False, True, "a", [{"user_id": 5, "username": "a"}])
    assert asked == ["profiles", "profiles"]


def test_a_read_of_a_missing_table_is_still_swallowed(tmp_path):
    # get_all_profiles on a file without the table returns nothing, as before
    path = tmp_path / "user_data.db"
    path.touch()
    assert asyncio.run(profile.get_all_profiles(db_path=path)) is None
