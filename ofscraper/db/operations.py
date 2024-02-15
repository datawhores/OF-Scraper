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
import contextlib
import logging
import math
import pathlib
import shutil
import sqlite3
from collections import abc
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import arrow
from filelock import FileLock
from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.paths.common as common_paths
from ofscraper.utils.context.run_async import run

from ..db import queries

console = Console()
log = logging.getLogger("shared")
# print error


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
            database_path = placeholder.Placeholders().databasePathHelper(
                kwargs.get("model_id"), kwargs.get("username")
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(database_path, check_same_thread=False, timeout=10)
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
            database_path = placeholder.Placeholders().databasePathHelper(
                kwargs.get("model_id"), kwargs.get("username")
            )
            database_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(database_path, check_same_thread=True, timeout=10)
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


@operation_wrapper
def create_message_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesCreate)
        conn.commit()


def write_messages_table(messages: dict, **kwargs):
    @operation_wrapper
    def inner(messages=None, conn=None, **kwargs):
        with contextlib.closing(conn.cursor()) as cur:
            messages = converthelper(messages)
            if len(messages) == 0:
                return
            insertData = list(
                map(
                    lambda message: (
                        message.id,
                        message.db_text,
                        message.price,
                        message.paid,
                        message.archived,
                        message.date,
                        message.model_id,
                    ),
                    messages,
                )
            )
            cur.executemany(queries.messagesInsert, insertData)
            conn.commit()

    return inner(messages=messages, **kwargs)


@operation_wrapper
def get_all_messages_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allMessagesCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def get_messages_data(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesData)
        conn.commit()
        return list(
            map(
                lambda x: {"date": arrow.get(x[0]).float_timestamp, "id": x[1]},
                cur.fetchall(),
            )
        )


def get_last_message_date(model_id=None, username=None):
    data = get_messages_data(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x.get("date"))[-1].get("date")


@operation_wrapper
def write_post_table(posts: list, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        posts = converthelper(posts)
        if len(posts) == 0:
            return
        insertData = list(
            map(
                lambda data: (
                    data.id,
                    data.db_text,
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                ),
                posts,
            )
        )
        cur.executemany(queries.postInsert, insertData)
        conn.commit()


@operation_wrapper
def get_timeline_postdates(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.timelinePostDates)
        conn.commit()
        return list(map(lambda x: arrow.get(x[0]).float_timestamp, cur.fetchall()))


@operation_wrapper
def create_post_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postCreate)
        conn.commit()


@operation_wrapper
def get_all_post_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allPOSTCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def create_stories_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.storiesCreate)
        conn.commit()


@operation_wrapper
def write_stories_table(stories: dict, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        stories = converthelper(stories)
        insertData = list(
            map(
                lambda data: (
                    data.id,
                    data.db_text or data.title or "",
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                ),
                stories,
            )
        )
        cur.executemany(queries.storiesInsert, insertData)
        conn.commit()


@operation_wrapper
def get_all_stories_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allStoriesCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def create_media_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaCreate)
        conn.commit()


@operation_wrapper
def get_media_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allIDCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def get_media_ids_downloaded(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allDLIDCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def get_profile_info(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.Placeholders().databasePathHelper(model_id, username)
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            modelinfo = cur.execute(
                queries.profileDupeCheck, (model_id,)
            ).fetchall() or [(None,)]
            conn.commit()
            return modelinfo[0][-1]
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@operation_wrapper_async
def update_media_table(
    media, filename=None, conn=None, downloaded=None, **kwargs
) -> list:
    prevData = conn.execute(queries.mediaDupeCheck, (media.id,)).fetchall()
    if len(prevData) == 0:
        insertData = media_insert_helper(media, filename, downloaded)
        conn.execute(queries.mediaInsert, insertData)
    else:
        insertData = media_insert_helper(media, filename, downloaded, prevData)
        insertData.append(media.id)
        conn.execute(queries.mediaUpdate, insertData)
    conn.commit()


def media_insert_helper(media, filename, downloaded, prevData=None):
    prevData = prevData[0] if isinstance(prevData, list) else prevData
    directory = None
    filename_path = None
    size = None
    if filename and pathlib.Path(filename).exists():
        directory = str(pathlib.Path(filename).parent)
        filename_path = str(pathlib.Path(filename))
        size = math.ceil(pathlib.Path(filename).stat().st_size)
    elif filename:
        directory = str(pathlib.Path(filename).parent)
        filename_path = str(pathlib.Path(filename))
    elif prevData:
        directory = prevData[3]
        filename_path = prevData[4]
        size = prevData[5]
    downloaded = downloaded
    if prevData:
        downloaded = prevData[-2] if downloaded == None else downloaded
    elif filename:
        downloaded = (
            pathlib.Path(filename).exists() if downloaded == None else downloaded
        )
    insertData = [
        media.id,
        media.postid,
        media.url,
        directory,
        filename_path,
        size,
        media.responsetype.capitalize(),
        media.mediatype.capitalize(),
        media.preview,
        media.linked,
        downloaded,
        media.date,
    ]
    return insertData


@operation_wrapper_async
def write_media_table_batch(medias, conn=None, **kwargs) -> list:
    medias = converthelper(medias)
    if len(medias) == 0:
        return
    insertData = list(
        map(
            lambda media: media_insert_helper(media, None, None),
            medias,
        )
    )
    conn.executemany(queries.mediaInsert, insertData)
    conn.commit()


@operation_wrapper
def get_timeline_media(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getTimelineMedia)
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


def get_last_timeline_date(model_id=None, username=None):
    data = get_timeline_postdates(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x)[-1]


@operation_wrapper
def get_archived_media(conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getArchivedMedia)
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


@operation_wrapper
def get_archived_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.archivedPostInfo)
        conn.commit()
        return list(
            map(lambda x: (arrow.get(x[0]).float_timestamp, x[1]), cur.fetchall())
        )


def get_last_archived_date(model_id=None, username=None):
    data = get_archived_postinfo(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x[0])[-1][0]


@operation_wrapper
def get_messages_media(conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getMessagesMedia)
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


@run
async def batch_mediainsert(media, funct, **kwargs):
    curr = set(get_media_ids(**kwargs) or [])
    mediaDict = {}
    for ele in media:
        mediaDict[ele.id] = ele
    await funct(list(filter(lambda x: x.id not in curr, mediaDict.values())), **kwargs)


@operation_wrapper_async
def update_response_media_table(medias, conn=None, downloaded=False, **kwargs) -> list:
    medias = converthelper(medias)
    insertData = list(
        map(
            lambda media: [
                media.responsetype.capitalize(),
                media.mediatype.capitalize(),
                media.id,
            ],
            medias,
        )
    )
    conn.executemany(queries.mediaTypeUpdate, insertData)
    conn.commit()


@operation_wrapper
def create_products_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.productCreate)
        conn.commit()


@operation_wrapper
def create_others_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.otherCreate)
        conn.commit()


@operation_wrapper
def create_profile_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.profilesCreate)
        conn.commit()


@operation_wrapper
def write_profile_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [model_id, username]
        if len(cur.execute(queries.profileDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(queries.profileInsert, insertData)
        else:
            insertData.append(model_id)
            cur.execute(queries.profileUpdate, insertData)
        conn.commit()


@operation_wrapper
def check_profile_table_exists(model_id=None, username=None, conn=None):
    database_path = placeholder.Placeholders().databasePathHelper(model_id, username)
    if not pathlib.Path(database_path).exists():
        return False
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.profileTableCheck).fetchall()) > 0:
            conn.commit()
            return True
        conn.commit()
        return False


@operation_wrapper
def create_labels_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.labelsCreate)
        conn.commit()


@operation_wrapper
def write_labels_table(
    label: dict, posts: dict, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(lambda post: (label.label_id, label.name, label.type, post.id), posts)
        )
        curr.executemany(queries.labelInsert, insertData)
        conn.commit()


@operation_wrapper
def get_all_labels_ids(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as curr:
        curr.execute(queries.labelID)
        conn.commit()
        return curr.fetchall()


def converthelper(media):
    if isinstance(media, list):
        return media
    elif isinstance(media, filter):
        return list(filter)
    else:
        return [media]


def create_tables(model_id, username):
    create_post_table(model_id=model_id, username=username)
    create_message_table(model_id=model_id, username=username)
    create_media_table(model_id=model_id, username=username)
    create_products_table(model_id=model_id, username=username)
    create_others_table(model_id=model_id, username=username)
    create_profile_table(model_id=model_id, username=username)
    create_stories_table(model_id=model_id, username=username)
    create_labels_table(model_id=model_id, username=username)


def create_backup(model_id, username):
    database_path = placeholder.Placeholders().databasePathHelper(model_id, username)

    now = arrow.now().float_timestamp
    last = cache.get(f"{username}_{model_id}_db_backup", default=now)
    if now - last > constants.getattr("DBINTERVAL") and database_path.exists():
        database_copy = placeholder.Placeholders().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    elif (
        not pathlib.Path(database_path.parent / "backup").exists()
        or len(list(pathlib.Path(database_path.parent / "backup").iterdir())) == 0
    ):
        database_copy = placeholder.Placeholders().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    cache.close()
