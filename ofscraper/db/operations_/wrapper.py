import asyncio
import logging
import pathlib
import sqlite3
from collections import abc
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.context.exit as exit
import ofscraper.utils.of_env.of_env as of_env  # Added for env vars

log = logging.getLogger("shared")

# Shared pool to serialize DB access and prevent thread thrashing
_DB_POOL = ThreadPoolExecutor(max_workers=1)


def operation_wrapper_async(func: abc.Callable):
    async def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        # Use the env variable 'DATABASE_TIMEOUT' (default 300s)
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")

        # Define the actual work to be executed safely inside the single-worker thread pool
        def _db_work():
            conn = None
            try:
                database_path = pathlib.Path(
                    kwargs.get("db_path", None)
                    or placeholder.databasePlaceholder().databasePathHelper(
                        kwargs.get("model_id"), kwargs.get("username")
                    )
                )
                database_path.parent.mkdir(parents=True, exist_ok=True)

                # Apply the user-configurable timeout here
                conn = sqlite3.connect(
                    database_path, check_same_thread=False, timeout=db_timeout
                )
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")

                # Limit memory-mapping to 256MB
                conn.execute("PRAGMA mmap_size=268435456;")

                # Give SQLite exactly 32MB of RAM for its active cache
                conn.execute("PRAGMA cache_size=-32768;")

                conn.row_factory = sqlite3.Row

                # Execute the database logic
                return func(*args, **kwargs, conn=conn)

            except Exception as E:
                log.debug(f"Database operation failed: {E}")
                raise E
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Submit the entire connection block to the safe pool
        return await loop.run_in_executor(_DB_POOL, _db_work)

    return inner


def operation_wrapper(func: abc.Callable):
    def inner(*args, **kwargs):
        conn = None
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")
        try:
            database_path = pathlib.Path(
                kwargs.get("db_path", None)
                or placeholder.databasePlaceholder().databasePathHelper(
                    kwargs.get("model_id"), kwargs.get("username")
                )
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)

            # Apply the user-configurable timeout for synchronous calls
            conn = sqlite3.connect(
                database_path, check_same_thread=True, timeout=db_timeout
            )

            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")

            # 2. The RAM-Safe Speed Boosters
            # Limit memory-mapping to 256MB so we don't choke a 2GB RAM system
            conn.execute("PRAGMA mmap_size=268435456;")

            # Give SQLite exactly 32MB of RAM for its active cache
            conn.execute("PRAGMA cache_size=-32768;")

            conn.row_factory = sqlite3.Row
            return func(*args, **kwargs, conn=conn)

        except sqlite3.OperationalError as E:
            log.info(f"Database is busy. Current timeout is {db_timeout}s.")
            raise E
        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        except Exception as E:
            raise E
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    return inner
