r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import asyncio
import logging
import pathlib
import sqlite3
from collections import abc
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from filelock import FileLock
from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.context.exit as exit
import ofscraper.utils.paths.common as common_paths

console = Console()
log = logging.getLogger("shared")


def operation_wrapper_async(func: abc.Callable):
    async def inner(*args, **kwargs):
        LOCK_POOL = None
        PROCESS_POOL = None
        lock = None
        loop = None
        conn = None
        try:
            LOCK_POOL = ThreadPoolExecutor()
            PROCESS_POOL = ThreadPoolExecutor(max_workers=1)
            lock = FileLock(common_paths.getDB(), timeout=-1)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(LOCK_POOL, lock.acquire)
            database_path = pathlib.Path(
                kwargs.get("db_path", None)
                or placeholder.databasePlaceholder().databasePathHelper(
                    kwargs.get("model_id"), kwargs.get("username")
                )
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(database_path, check_same_thread=False, timeout=10)
            conn.row_factory = sqlite3.Row
            return await loop.run_in_executor(
                PROCESS_POOL, partial(func, *args, **kwargs, conn=conn)
            )
        except sqlite3.OperationalError as E:
            log.info("DB may be locked")
            raise E
        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                if lock:
                    lock.release(True)
                if conn:
                    conn.close()
                if LOCK_POOL:
                    LOCK_POOL.shutdown()
                if PROCESS_POOL:
                    PROCESS_POOL.shutdown()
                raise E
        except Exception as E:
            raise E
        finally:
            if conn:
                conn.close()
            if lock:
                await loop.run_in_executor(LOCK_POOL, partial(lock.release, force=True))
            if LOCK_POOL:
                LOCK_POOL.shutdown()
            if PROCESS_POOL:
                PROCESS_POOL.shutdown()
            log.trace("Force Closing DB")

    return inner


def operation_wrapper(func: abc.Callable):
    def inner(*args, **kwargs):
        try:
            lock = FileLock(common_paths.getDB(), timeout=-1)
        except Exception as E:
            raise E
        try:
            lock.acquire(timeout=-1)
            database_path = pathlib.Path(
                kwargs.get("db_path", None)
                or placeholder.databasePlaceholder().databasePathHelper(
                    kwargs.get("model_id"), kwargs.get("username")
                )
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(database_path, check_same_thread=True, timeout=10)
            conn.row_factory = sqlite3.Row
            return func(*args, **kwargs, conn=conn)
        except sqlite3.OperationalError as E:
            log.info("DB may be locked")
            raise E
        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                try:
                    lock.release(force=True)
                except:
                    None
                try:
                    conn.close()
                except:
                    None
                raise E

        except Exception as E:
            raise E
        finally:
            try:
                conn.close()
            except:
                None
            try:
                lock.release(force=True)
            except:
                None
            log.trace("Force Closing DB")

    return inner
