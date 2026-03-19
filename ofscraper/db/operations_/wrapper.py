import asyncio
import logging
import pathlib
import sqlite3
from collections import abc
from concurrent.futures import ThreadPoolExecutor

import tenacity 

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.context.exit as exit
import ofscraper.utils.of_env.of_env as of_env  # Added for env vars

log = logging.getLogger("shared")

# Shared pool to serialize DB access and prevent thread thrashing
_DB_POOL = ThreadPoolExecutor(max_workers=1)


def operation_wrapper_async(func: abc.Callable):
    async def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")

        # Wrap the inner DB work with Tenacity to handle multiprocess deadlocks gracefully
        @tenacity.retry(
            retry=tenacity.retry_if_exception_type(sqlite3.OperationalError),
            wait=tenacity.wait_random_exponential(multiplier=0.5, max=10),
            stop=tenacity.stop_after_attempt(5),
            reraise=True
        )
        def _db_work():
            conn = None
            try:
                database_path = pathlib.Path(
                    kwargs.get("db_path", None)
                    or placeholder.databasePlaceholder().databasePathHelper(
                        kwargs.get("model_id"), kwargs.get("username")
                    )
                ).resolve()
                database_path.parent.mkdir(parents=True, exist_ok=True)

                conn = sqlite3.connect(
                    database_path, check_same_thread=False, timeout=db_timeout
                )
                
                # 1. Set the PRAGMAs FIRST (Configure the engine)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA mmap_size=268435456;")
                conn.execute("PRAGMA cache_size=-32768;")
                conn.row_factory = sqlite3.Row

                # 2. THEN grab the write lock
                conn.execute("BEGIN IMMEDIATE;")

                # 3. Execute the database logic
                result = func(*args, **kwargs, conn=conn)
                return result

            except Exception as E:
                log.debug(f"Database operation failed: {E}")
                raise E
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Submit the safe retry block to the pool
        return await loop.run_in_executor(_DB_POOL, _db_work)

    return inner


def operation_wrapper(func: abc.Callable):
    # Apply Tenacity retry directly to the inner sync function
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(sqlite3.OperationalError),
        wait=tenacity.wait_random_exponential(multiplier=0.5, max=10),
        stop=tenacity.stop_after_attempt(5),
        reraise=True
    )
    def inner(*args, **kwargs):
        conn = None
        db_timeout = of_env.getattr("DATABASE_TIMEOUT")
        try:
            database_path = pathlib.Path(
                kwargs.get("db_path", None)
                or placeholder.databasePlaceholder().databasePathHelper(
                    kwargs.get("model_id"), kwargs.get("username")
                )
            ).resolve()
            database_path.parent.mkdir(parents=True, exist_ok=True)

            # Apply the user-configurable timeout for synchronous calls
            conn = sqlite3.connect(
                database_path, check_same_thread=True, timeout=db_timeout
            )

            # 1. Set the PRAGMAs FIRST
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            # The RAM-Safe Speed Boosters
            conn.execute("PRAGMA mmap_size=268435456;")
            conn.execute("PRAGMA cache_size=-32768;")
            
            conn.row_factory = sqlite3.Row
            
            conn.execute("BEGIN IMMEDIATE;")

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