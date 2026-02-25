import asyncio
import logging
import pathlib
import sqlite3
from collections import abc
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.context.exit as exit

log = logging.getLogger("shared")

# A single global pool to handle DB operations one at a time.
# This prevents 2GB RAM systems from being overwhelmed by threads.
_DB_POOL = ThreadPoolExecutor(max_workers=1)

def operation_wrapper_async(func: abc.Callable):
    async def inner(*args, **kwargs):
        conn = None
        loop = asyncio.get_event_loop()
        try:
            database_path = pathlib.Path(
                kwargs.get("db_path", None)
                or placeholder.databasePlaceholder().databasePathHelper(
                    kwargs.get("model_id"), kwargs.get("username")
                )
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(database_path, check_same_thread=False, timeout=200)
            conn.row_factory = sqlite3.Row
            # Execute the DB function in our serialized global pool.
            return await loop.run_in_executor(
                _DB_POOL, partial(func, *args, **kwargs, conn=conn)
            )

        except Exception as E:
            log.debug(f"Database operation failed: {E}")
            raise E
        finally:
            if conn:
                conn.close()
    return inner

def operation_wrapper(func: abc.Callable):
    def inner(*args, **kwargs):
        conn = None
        try:
            database_path = pathlib.Path(
                kwargs.get("db_path", None)
                or placeholder.databasePlaceholder().databasePathHelper(
                    kwargs.get("model_id"), kwargs.get("username")
                )
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Standard synchronous connection with internal timeout.
            conn = sqlite3.connect(database_path, check_same_thread=True, timeout=200)
            conn.row_factory = sqlite3.Row
            return func(*args, **kwargs, conn=conn)
            
        except sqlite3.OperationalError as E:
            log.info("Database is currently busy.")
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