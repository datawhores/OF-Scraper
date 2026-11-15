"""The database wrappers' connection handling.

operation_wrapper (sync) and operation_wrapper_async share one connect,
PRAGMA, BEGIN and close sequence. These tests pin what each does: the
connection's settings, that the wrapped function commits (the wrapper
doesn't), what happens on an error, a locked database or a supplied conn,
and that the connection is always closed.
"""

import asyncio
import contextlib
import logging
import sqlite3
import threading

import pytest
import tenacity

import ofscraper.db.operations_.wrapper as wrapper

WRAPPERS = {
    "sync": lambda func: wrapper.operation_wrapper(func),
    "async": lambda func: (
        lambda *a, **k: asyncio.run(wrapper.operation_wrapper_async(func)(*a, **k))
    ),
}


@pytest.fixture(params=list(WRAPPERS))
def wrap(request):
    """Decorate a function with one wrapper; calling it runs it to the end."""
    wrap = WRAPPERS[request.param]
    wrap.kind = request.param
    return wrap


@pytest.fixture
def opened(monkeypatch):
    """The connections the wrapper opens, one per try."""
    connections = []
    real = wrapper._connect

    def connect(*args, **kwargs):
        conn = real(*args, **kwargs)
        connections.append(conn)
        return conn

    monkeypatch.setattr(wrapper, "_connect", connect)
    yield connections
    for conn in connections:
        conn.close()


@pytest.fixture
def no_wait(monkeypatch):
    """tenacity's waits between tries, recorded instead of slept."""
    waits = []
    monkeypatch.setattr(tenacity.nap.time, "sleep", waits.append)
    return waits


def make_db(path, wal=False):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        if wal:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (x)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()


def rows(path):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return [row[0] for row in conn.execute("SELECT x FROM t ORDER BY x")]


def is_closed(conn):
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


@pytest.mark.parametrize("read_only", [False, True], ids=["write", "read"])
def test_connection_settings(tmp_path, wrap, opened, read_only):
    path = tmp_path / "user_data.db"
    make_db(path)
    seen = {}

    def func(conn=None, **kwargs):
        seen["conn"] = conn
        seen["thread"] = threading.get_ident()
        seen["in_transaction"] = conn.in_transaction
        seen["row"] = conn.execute("SELECT x FROM t").fetchone()
        for pragma in ("journal_mode", "synchronous", "mmap_size", "cache_size"):
            seen[pragma] = conn.execute(f"PRAGMA {pragma}").fetchone()[0]
        errors = []

        def other_thread():
            try:
                conn.execute("SELECT 1")
            except sqlite3.ProgrammingError as error:
                errors.append(error)

        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join()
        seen["other_thread_refused"] = bool(errors)
        return "result"

    assert wrap(func)(db_path=path, read_only=read_only) == "result"
    assert len(opened) == 1
    assert seen["conn"] is opened[0]
    assert isinstance(seen["row"], sqlite3.Row)
    assert seen["in_transaction"]
    assert seen["mmap_size"] == 268435456
    assert seen["cache_size"] == -32768
    if read_only:
        assert seen["journal_mode"] == "delete"
        assert seen["synchronous"] == 2  # FULL, sqlite's default
    else:
        assert seen["journal_mode"] == "wal"
        assert seen["synchronous"] == 1  # NORMAL
    # async runs on the pool's thread and allows other threads; sync
    # runs on the caller's thread and doesn't
    on_caller = seen["thread"] == threading.get_ident()
    assert on_caller is (wrap.kind == "sync")
    assert seen["other_thread_refused"] is (wrap.kind == "sync")
    assert is_closed(opened[0])


def test_read_only_takes_no_write_lock(tmp_path, wrap, opened):
    path = tmp_path / "user_data.db"
    make_db(path, wal=True)
    with contextlib.closing(sqlite3.connect(path)) as holder:
        holder.execute("BEGIN IMMEDIATE")
        result = wrap(
            lambda conn=None, **kwargs: conn.execute("SELECT x FROM t").fetchall()[0][0]
        )(db_path=path, read_only=True)
        holder.rollback()
    assert result == 1
    assert len(opened) == 1


def test_wrapper_does_not_commit(tmp_path, wrap, opened):
    # the wrapped function commits; what it leaves uncommitted is dropped
    path = tmp_path / "user_data.db"
    make_db(path)

    def func(conn=None, **kwargs):
        conn.execute("INSERT INTO t VALUES (2)")
        conn.commit()
        conn.execute("INSERT INTO t VALUES (3)")

    wrap(func)(db_path=path)
    assert rows(path) == [1, 2]
    assert is_closed(opened[0])


def test_error_rolls_back_and_is_not_retried(tmp_path, wrap, opened, no_wait):
    path = tmp_path / "user_data.db"
    make_db(path)

    class Failure(Exception):
        pass

    def func(conn=None, **kwargs):
        conn.execute("INSERT INTO t VALUES (2)")
        raise Failure("boom")

    with pytest.raises(Failure, match="boom"):
        wrap(func)(db_path=path)
    assert rows(path) == [1]
    assert len(opened) == 1
    assert is_closed(opened[0])
    assert no_wait == []


def test_sql_error_in_function_is_retried(tmp_path, wrap, opened, no_wait):
    # any OperationalError is retried, even a mistake in the SQL itself
    path = tmp_path / "user_data.db"
    make_db(path)

    def func(conn=None, **kwargs):
        conn.execute("SELECT FROM nowhere")

    with pytest.raises(sqlite3.OperationalError, match="syntax error") as raised:
        wrap(func)(db_path=path)
    assert raised.value.database_path == path.resolve()
    assert len(opened) == 5
    assert all(is_closed(conn) for conn in opened)
    assert len(no_wait) == 4


def test_supplied_conn_is_refused(tmp_path, wrap, opened, no_wait):
    # the wrapper always opens its own connection; a caller's conn clashes
    path = tmp_path / "user_data.db"
    make_db(path)
    with contextlib.closing(sqlite3.connect(path)) as own:
        with pytest.raises(TypeError, match="multiple values for keyword"):
            wrap(lambda conn=None, **kwargs: None)(db_path=path, conn=own)
        assert not is_closed(own)
    assert len(opened) == 1
    assert is_closed(opened[0])
    assert no_wait == []


def test_locked_database(tmp_path, wrap, opened, no_wait, monkeypatch, caplog):
    path = tmp_path / "user_data.db"
    make_db(path, wal=True)
    real_getattr = wrapper.of_env.getattr
    monkeypatch.setattr(
        wrapper.of_env,
        "getattr",
        lambda key, *args, **kwargs: (
            0.05 if key == "DATABASE_TIMEOUT" else real_getattr(key, *args, **kwargs)
        ),
    )
    called = []
    with contextlib.closing(sqlite3.connect(path)) as holder:
        holder.execute("BEGIN IMMEDIATE")
        with caplog.at_level(logging.DEBUG, logger="shared"):
            with pytest.raises(sqlite3.OperationalError, match="locked") as raised:
                wrap(lambda conn=None, **kwargs: called.append(1))(db_path=path)
        holder.rollback()
    assert raised.value.database_path == path.resolve()
    assert called == []
    assert len(opened) == 5
    assert all(is_closed(conn) for conn in opened)
    assert len(no_wait) == 4
    messages = [
        (record.levelno, record.getMessage())
        for record in caplog.records
        if record.name == "shared"
    ]
    if wrap.kind == "sync":
        expected = (logging.INFO, "Database is busy. Current timeout is 0.05s.")
    else:
        expected = (logging.DEBUG, "Database operation failed: database is locked")
    assert messages == [expected] * 5


class CloseFails:
    """A connection whose close() closes it, then raises `error`."""

    def __init__(self, conn, error):
        self._conn = conn
        self._error = error

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def close(self):
        self._conn.close()
        raise self._error


def test_close_error_is_ignored(tmp_path, wrap, monkeypatch):
    path = tmp_path / "user_data.db"
    make_db(path)
    real_connect = wrapper._connect
    monkeypatch.setattr(
        wrapper,
        "_connect",
        lambda *args, **kwargs: CloseFails(
            real_connect(*args, **kwargs), sqlite3.ProgrammingError("close")
        ),
    )
    assert wrap(lambda conn=None, **kwargs: "result")(db_path=path) == "result"


def test_interrupt_while_closing_is_not_swallowed(tmp_path, monkeypatch):
    # the sync wrapper's close guard was a bare except, which also caught
    # KeyboardInterrupt and returned as if nothing happened
    path = tmp_path / "user_data.db"
    make_db(path)
    real_connect = wrapper._connect
    monkeypatch.setattr(
        wrapper,
        "_connect",
        lambda *args, **kwargs: CloseFails(
            real_connect(*args, **kwargs), KeyboardInterrupt()
        ),
    )
    with pytest.raises(KeyboardInterrupt):
        wrapper.operation_wrapper(lambda conn=None, **kwargs: "result")(db_path=path)
