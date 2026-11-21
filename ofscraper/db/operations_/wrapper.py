import asyncio
import logging
import pathlib
import sqlite3
import urllib.parse
from collections import abc
from concurrent.futures import ThreadPoolExecutor

import tenacity

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")

# Shared pool with 1 worker to serialize DB writes and prevent "database is locked" errors
_DB_POOL = ThreadPoolExecutor(max_workers=1)


class DatabaseMissing(FileNotFoundError):
    """A read-only read found no database: no file, or a file without the
    table (older `ofscraper db` runs left empty files). Not an sqlite error,
    so it isn't retried."""


class DatabaseUnreadable(sqlite3.DatabaseError):
    """The database file can't be opened. A retry can't fix that, so it
    isn't retried."""


def _final_error(error, read_only, database_path):
    """The error to raise for `error` (#373), for the caller to tell apart:
    "unable to open database file" always becomes DatabaseUnreadable, and
    "no such table" on the read-only path DatabaseMissing. Neither is
    retried (see _retryable). An sqlite error carries the database's path
    (database_path) for messages."""
    message = str(error)
    if isinstance(error, sqlite3.OperationalError):
        if message.startswith("unable to open database file"):
            error = DatabaseUnreadable(message)
        elif read_only and message.startswith("no such table"):
            error = DatabaseMissing(message)
    if isinstance(error, sqlite3.DatabaseError):
        error.database_path = database_path
    return error


def _read_only_uri(database_path):
    """The file: URI that opens the database read-only, for a drive path, a
    UNC path or a POSIX path. Path.as_uri() puts a UNC path's server in the
    URI's host part, which SQLite can't open; SQLite takes //server/share
    after file:// (file:////server/share/...)."""
    path = urllib.parse.quote(database_path.as_posix(), safe="/:")
    return f"file://{'' if path.startswith('/') else '/'}{path}?mode=ro"


def _database_path(kwargs, read_only):
    """The operation's database: db_path, or the creator's usual path. A
    read-only read works that out without making the creator's folder
    (#373); a write makes it, as before."""
    if kwargs.get("db_path", None):
        return pathlib.Path(kwargs["db_path"]).resolve()
    holder = (
        placeholder.databasePlaceholder(create=False)
        if read_only
        else placeholder.databasePlaceholder()
    )
    return pathlib.Path(
        holder.databasePathHelper(kwargs.get("model_id"), kwargs.get("username"))
    ).resolve()


# The queries use TRUE and FALSE (SQLite 3.23) and INSERT ... ON CONFLICT
# (3.24, from 2018), which other databases understand too
MIN_SQLITE = (3, 24, 0)


def _check_sqlite_version():
    if sqlite3.sqlite_version_info < MIN_SQLITE:
        raise DatabaseUnreadable(
            f"this Python's SQLite is {sqlite3.sqlite_version}; "
            f"{'.'.join(map(str, MIN_SQLITE[:2]))} or newer is needed"
        )


def _connect(database_path, read_only, **kwargs):
    """Open the database. A caller that only reads passes read_only=True
    (#373): the file is opened read-only, so it isn't created, its journal
    mode isn't changed, and a read-only file can be read."""
    _check_sqlite_version()
    if read_only:
        if not database_path.is_file():
            raise DatabaseMissing(f"no database at {database_path}")
        return sqlite3.connect(_read_only_uri(database_path), uri=True, **kwargs)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(database_path, **kwargs)


# Primary result codes (an extended code's low byte) of the errors that can
# clear up on their own. Busy and locked: another connection holds the lock
# (a WAL switch while another connection is open is busy too). The others
# are retried as they always were: a WAL lock race (locking protocol), an
# I/O error, which can be a scanner or a network share holding the file for
# a moment, and a schema change made by another connection.
_BUSY_CODES = frozenset((sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED))
_RETRY_CODES = _BUSY_CODES | {
    sqlite3.SQLITE_PROTOCOL,
    sqlite3.SQLITE_IOERR,
    sqlite3.SQLITE_SCHEMA,
}
# SQLite's messages for those codes, for an error that carries no code (one
# raised by Python code rather than by SQLite)
_BUSY_MESSAGES = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
)
_RETRY_MESSAGES = _BUSY_MESSAGES + (
    "locking protocol",
    "disk I/O error",
    "database schema has changed",
)


def _has_code(error, codes, messages):
    if not isinstance(error, sqlite3.OperationalError):
        return False
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xFF in codes
    return str(error).startswith(messages)


def _busy(error):
    """Whether `error` is a busy or locked database."""
    return _has_code(error, _BUSY_CODES, _BUSY_MESSAGES)


def _retryable(error):
    """Whether a retry can fix `error`: a busy or locked database, or
    another condition that clears up on its own. A mistake in the wrapped
    function's SQL (a syntax error, no such table), a read-only or full
    database and one that can't be opened aren't retried."""
    return _has_code(error, _RETRY_CODES, _RETRY_MESSAGES)


def _retry(work):
    """Retry `work` on an error a retry can fix (see _retryable), as both
    wrappers do."""
    return tenacity.retry(
        retry=tenacity.retry_if_exception(_retryable),
        wait=tenacity.wait_random_exponential(multiplier=0.5, max=10),
        stop=tenacity.stop_after_attempt(5),
        reraise=True,
    )(work)


def _log_failure(error, db_timeout):
    """Log a failed try the same way for both wrappers: every failure at
    debug, and a busy or locked database at info, with the timeout that
    ran out."""
    log.debug(f"Database operation failed: {error}")
    if _busy(error):
        log.info(f"Database is busy. Current timeout is {db_timeout}s.")


def _run_operation(func, args, kwargs, *, read_only, db_timeout, check_same_thread):
    """One try of a database operation: open the database, configure it,
    begin a transaction, call func(*args, **kwargs, conn=conn) and close
    the connection. The wrapper doesn't commit: func commits what it keeps,
    and closing rolls back the rest.

    An error is logged (see _log_failure) and raised as _final_error makes
    it, `from` the error if that differs.
    """
    conn = None
    database_path = None
    try:
        database_path = _database_path(kwargs, read_only)
        conn = _connect(
            database_path,
            read_only,
            check_same_thread=check_same_thread,
            timeout=db_timeout,
        )

        # 1. Set the PRAGMAs FIRST (configure the engine)
        if not read_only:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        # The RAM-safe speed boosters
        conn.execute("PRAGMA mmap_size=268435456;")
        conn.execute("PRAGMA cache_size=-32768;")
        conn.row_factory = sqlite3.Row

        # 2. THEN grab the write lock (a read takes a read lock)
        conn.execute("BEGIN;" if read_only else "BEGIN IMMEDIATE;")

        # 3. Execute the database logic
        return func(*args, **kwargs, conn=conn)
    except Exception as E:
        _log_failure(E, db_timeout)
        failure = _final_error(E, read_only, database_path)
        if failure is not E:
            raise failure from E
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _refuse_conn(func, kwargs):
    """A wrapped function gets its connection from the wrapper, which
    opens one for each try; a conn from the caller can't be used."""
    if "conn" in kwargs:
        raise TypeError(
            f"{func.__name__}() was passed conn=, but its database wrapper"
            " opens and supplies the connection itself; call it without conn"
        )


def operation_wrapper_async(func: abc.Callable):
    async def inner(*args, **kwargs):
        _refuse_conn(func, kwargs)
        loop = asyncio.get_event_loop()
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")
        read_only = kwargs.get("read_only", False)

        # Retried inside the pool's thread, so a retry doesn't requeue
        @_retry
        def _db_work():
            return _run_operation(
                func,
                args,
                kwargs,
                read_only=read_only,
                db_timeout=db_timeout,
                # the connection is opened on the pool's thread
                check_same_thread=False,
            )

        # Submit the safe retry block to the single-worker pool
        return await loop.run_in_executor(_DB_POOL, _db_work)

    return inner


def operation_wrapper(func: abc.Callable):
    def inner(*args, **kwargs):
        _refuse_conn(func, kwargs)

        @_retry
        def _db_work():
            return _run_operation(
                func,
                args,
                kwargs,
                read_only=kwargs.get("read_only", False),
                db_timeout=of_env.getattr("DATABASE_TIMEOUT"),
                check_same_thread=True,
            )

        return _db_work()

    return inner
