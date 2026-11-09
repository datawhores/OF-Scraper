import asyncio
import logging
import pathlib
import sqlite3
import urllib.parse
from collections import abc
from concurrent.futures import ThreadPoolExecutor

import tenacity

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.context.exit as exit
import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")

# Shared pool with 1 worker to serialize DB writes and prevent "database is locked" errors
_DB_POOL = ThreadPoolExecutor(max_workers=1)


class DatabaseMissing(FileNotFoundError):
    """A read-only read found no database: no file, or a file without the
    table (older `ofscraper db` runs left empty files). Not an sqlite error,
    so it isn't retried."""


class DatabaseUnreadable(sqlite3.DatabaseError):
    """The database file can't be opened. A retry can't fix that, and only
    OperationalError is retried."""


def _final_error(error, read_only, database_path):
    """The error to raise for `error` (#373). One a retry can't fix is
    replaced by one that isn't an OperationalError, so it isn't retried:
    "unable to open database file" always, and "no such table" on the
    read-only path. Busy and locked errors are kept, and retried. An sqlite
    error carries the database's path (database_path) for messages."""
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


def _connect(database_path, read_only, **kwargs):
    """Open the database. A caller that only reads passes read_only=True
    (#373): the file is opened read-only, so it isn't created, its journal
    mode isn't changed, and a read-only file can be read."""
    if read_only:
        if not database_path.is_file():
            raise DatabaseMissing(f"no database at {database_path}")
        return sqlite3.connect(_read_only_uri(database_path), uri=True, **kwargs)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(database_path, **kwargs)


def operation_wrapper_async(func: abc.Callable):
    async def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")
        read_only = kwargs.get("read_only", False)

        # Wrap the inner DB work with Tenacity to handle async/thread collisions gracefully
        @tenacity.retry(
            retry=tenacity.retry_if_exception_type(sqlite3.OperationalError),
            wait=tenacity.wait_random_exponential(multiplier=0.5, max=10),
            stop=tenacity.stop_after_attempt(5),
            reraise=True,
        )
        def _db_work():
            conn = None
            database_path = None
            try:
                database_path = _database_path(kwargs, read_only)

                conn = _connect(
                    database_path,
                    read_only,
                    check_same_thread=False,
                    timeout=db_timeout,
                )

                # 1. Set the PRAGMAs FIRST (Configure the engine)
                if not read_only:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA mmap_size=268435456;")
                conn.execute("PRAGMA cache_size=-32768;")
                conn.row_factory = sqlite3.Row

                # 2. THEN grab the write lock (a read takes a read lock)
                conn.execute("BEGIN;" if read_only else "BEGIN IMMEDIATE;")

                # 3. Execute the database logic
                result = func(*args, **kwargs, conn=conn)
                return result

            except Exception as E:
                log.debug(f"Database operation failed: {E}")
                failure = _final_error(E, read_only, database_path)
                if failure is not E:
                    raise failure from E
                raise E
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Submit the safe retry block to the single-worker pool
        return await loop.run_in_executor(_DB_POOL, _db_work)

    return inner


def operation_wrapper(func: abc.Callable):
    # Apply Tenacity retry directly to the inner sync function
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(sqlite3.OperationalError),
        wait=tenacity.wait_random_exponential(multiplier=0.5, max=10),
        stop=tenacity.stop_after_attempt(5),
        reraise=True,
    )
    def inner(*args, **kwargs):
        conn = None
        database_path = None
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")
        read_only = kwargs.get("read_only", False)
        try:
            database_path = _database_path(kwargs, read_only)

            # Apply the user-configurable timeout for synchronous calls
            conn = _connect(
                database_path,
                read_only,
                check_same_thread=True,
                timeout=db_timeout,
            )

            # 1. Set the PRAGMAs FIRST
            if not read_only:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")

            # The RAM-Safe Speed Boosters
            conn.execute("PRAGMA mmap_size=268435456;")
            conn.execute("PRAGMA cache_size=-32768;")

            conn.row_factory = sqlite3.Row

            conn.execute("BEGIN;" if read_only else "BEGIN IMMEDIATE;")

            return func(*args, **kwargs, conn=conn)

        except sqlite3.OperationalError as E:
            failure = _final_error(E, read_only, database_path)
            if failure is not E:
                raise failure from E
            log.info(f"Database is busy. Current timeout is {db_timeout}s.")
            raise E
        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except Exception as E:
            raise _final_error(E, read_only, database_path)
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    return inner
