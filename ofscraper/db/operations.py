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
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
import ofscraper.utils.context.exit as exit
import ofscraper.utils.paths.common as common_paths
from ofscraper.utils.context.run_async import run

from ..db import queries

console = Console()
log = logging.getLogger("shared")
#################################################################################################
###
###   wrappers
###
#################################################################################################


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
            database_path = placeholder.databasePlaceholder().databasePathHelper(
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
            database_path = placeholder.databasePlaceholder().databasePathHelper(
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


#################################################################################################
###
###   Messages
###
#################################################################################################


@operation_wrapper
def create_message_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesCreate)
        conn.commit()


@operation_wrapper
def update_messages_table(messages: dict, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        updateData = list(
            map(
                lambda message: (
                    message.db_text,
                    message.price,
                    message.paid,
                    message.archived,
                    message.date,
                    message.fromuser,
                    model_id,
                    message.id,
                ),
                messages,
            )
        )
        cur.executemany(queries.messagesUpdate, updateData)
        conn.commit()


@operation_wrapper
def write_messages_table(messages: dict, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = list(
            map(
                lambda message: (
                    message.id,
                    message.db_text,
                    message.price,
                    message.paid,
                    message.archived,
                    message.date,
                    message.fromuser,
                    model_id,
                ),
                messages,
            )
        )
        cur.executemany(queries.messagesInsert, insertData)
        conn.commit()


@operation_wrapper
def write_messages_table_transition(
    insertData: list, model_id=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.messagesInsert, insertData)
        conn.commit()


@operation_wrapper
def get_all_messages_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesALL)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def get_all_messages_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesALLTransition)
        conn.commit()
        return cur.fetchall()


@operation_wrapper
def drop_messages_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesDrop)
        conn.commit()


@operation_wrapper
def get_messages_progress_data(
    model_id=None, username=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesData, model_id)
        conn.commit()
        return list(
            map(
                lambda x: {"date": arrow.get(x[0]).float_timestamp, "id": x[1]},
                cur.fetchall(),
            )
        )


#################################################################################################
###
###   posts
###
#################################################################################################


@operation_wrapper
def write_post_table(posts: list, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = list(
            map(
                lambda data: (
                    data.id,
                    data.db_text,
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                    model_id,
                ),
                posts,
            )
        )
        cur.executemany(queries.postInsert, insertData)
        conn.commit()


@operation_wrapper
def write_post_table_transition(
    insertData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.postInsert, insertData)
        conn.commit()


@operation_wrapper
def update_posts_table(posts: list, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        updateData = list(
            map(
                lambda data: [
                    data.db_text,
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                    data.id,
                    model_id,
                ],
                posts,
            )
        )
        cur.executemany(queries.postUpdate, updateData)
        conn.commit()


@operation_wrapper
def get_timeline_postdates(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.timelinePostDates, [model_id])
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
def get_all_posts_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postsALLTransition)
        conn.commit()
        return cur.fetchall()


@operation_wrapper
def drop_posts_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postsDrop)
        conn.commit()


@operation_wrapper
def add_column_post_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.profileAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


#################################################################################################
###
###   stories
###
#################################################################################################


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
                    model_id,
                ),
                stories,
            )
        )
        cur.executemany(queries.storiesInsert, insertData)
        conn.commit()


@operation_wrapper
def write_stories_table_transition(
    insertData: dict, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.storiesInsert, insertData)
        conn.commit()


@operation_wrapper
def update_stories_table(stories: dict, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        stories = converthelper(stories)
        updateData = list(
            map(
                lambda data: (
                    data.db_text or data.title or "",
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                    data.id,
                    model_id,
                ),
                stories,
            )
        )
        cur.executemany(queries.storiesUpdate, updateData)
        conn.commit()


@operation_wrapper
def get_all_stories_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allStoriesCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def get_all_stories_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.storiesALLTransition)
        conn.commit()
        return cur.fetchall()


@operation_wrapper
def add_column_stories_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.storiesAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@operation_wrapper
def drop_stories_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.storiesDrop)
        conn.commit()


#################################################################################################
###
###   media
###
#################################################################################################


@operation_wrapper
def create_media_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaCreate)
        conn.commit()


@operation_wrapper
def add_column_media_hash(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.mediaAddColumnHash)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: hash":
                raise E


@operation_wrapper
def add_column_media_ID(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.mediaAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


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
def get_dupe_media_hashes(
    model_id=None, username=None, conn=None, mediatype=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        if mediatype:
            cur.execute(queries.mediaDupeHashesMedia, [mediatype])
        else:
            cur.execute(queries.mediaDupeHashes)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper
def get_dupe_media_files(
    model_id=None, username=None, conn=None, hash=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaDupeFiles, [hash])
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@operation_wrapper_async
def download_media_update(
    media,
    model_id=None,
    conn=None,
    filename=None,
    downloaded=None,
    hashdata=None,
    **kwargs,
):
    with contextlib.closing(conn.cursor()) as curr:
        update_media_table_via_api_helper(media, model_id=model_id, conn=curr)
        update_media_table_download_helper(
            media,
            filename=filename,
            hashdata=hashdata,
            conn=curr,
            downloaded=downloaded,
        )
        conn.commit()


@operation_wrapper_async
def write_media_table_via_api_batch(medias, model_id=None, conn=None, **kwargs) -> list:
    insertData = list(
        map(
            lambda media: [
                media.id,
                media.postid,
                media.url,
                None,
                None,
                None,
                media.responsetype.capitalize(),
                media.mediatype.capitalize(),
                media.preview,
                media.linked,
                None,
                media.date,
                None,
                model_id,
            ],
            medias,
        )
    )

    conn.executemany(queries.mediaInsert, insertData)
    conn.commit()


@operation_wrapper
def write_media_table_transition(insertData, model_id=None, conn=None, **kwargs):
    insertData = [[*ele, model_id] for ele in insertData]
    conn.executemany(queries.mediaInsert, insertData)
    conn.commit()


@operation_wrapper
def get_all_medias_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaALLTransition)
        conn.commit()
        return cur.fetchall()


@operation_wrapper
def drop_media_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaDrop)
        conn.commit()


#################################################################################################
###
###   profile
#################################################################################################


@operation_wrapper
def get_profile_info(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
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
def write_profile_table_transition(insertData, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(queries.profileInsert, insertData)
        conn.commit()


@operation_wrapper
def check_profile_table_exists(model_id=None, username=None, conn=None):
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return False
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.profileTableCheck).fetchall()) > 0:
            conn.commit()
            return True
        conn.commit()
        return False


@operation_wrapper
def checker_profile_unique(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profileInfo = cur.execute(queries.checkProfileTableUnique).fetchall()
            if not bool(profileInfo):
                return
            conn.commit()
            return profileInfo[0][2] == 1
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@operation_wrapper
def get_all_profiles(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profiles = cur.execute(queries.profilesALL).fetchall()
            conn.commit()
            return profiles
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@operation_wrapper
def drop_profiles_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.profilesDrop)
        conn.commit()


#################################################################################################
###
###   models
###
#################################################################################################
@operation_wrapper
def create_models_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.modelsCreate)
        conn.commit()


#################################################################################################
###
###   labels
###
#################################################################################################


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
            map(
                lambda post: (label.label_id, label.name, label.type, post.id, model_id)
                if not isinstance(posts, tuple)
                else post,
                posts,
            )
        )
        curr.executemany(queries.labelInsert, insertData)
        conn.commit()


@operation_wrapper
def write_labels_table_transition(
    insertData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as curr:
        insertData = [[*ele, model_id] for ele in insertData]
        curr.executemany(queries.labelInsert, insertData)
        conn.commit()


@operation_wrapper
def get_all_labels_ids(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as curr:
        curr.execute(queries.labelID)
        conn.commit()
        return curr.fetchall()


@operation_wrapper
def add_column_labels_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.labelAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@operation_wrapper
def drop_labels_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.labelDrop)
        conn.commit()


@operation_wrapper
def get_all_labels_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.labelALLTransition)
            return cur.fetchall()
        except sqlite3.OperationalError:
            cur.execute(queries.labelALLTransition2)
            return cur.fetchall()


#################################################################################################
###
###   apis
###
#################################################################################################


@operation_wrapper
def get_timeline_media(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getTimelineMedia, [model_id])
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


def get_last_timeline_date(model_id=None, username=None):
    data = get_timeline_postdates(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x)[-1]


@operation_wrapper
def get_archived_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getArchivedMedia, [model_id])
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


@operation_wrapper
def get_archived_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.archivedPostInfo, [model_id])
        conn.commit()
        return list(
            map(lambda x: (arrow.get(x[0]).float_timestamp, x[1]), cur.fetchall())
        )


def get_last_archived_date(model_id=None, username=None):
    data = get_archived_postinfo(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x[0])[-1][0]


@operation_wrapper
def get_messages_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getMessagesMedia, [model_id])
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


@operation_wrapper
def add_column_messages_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.messagesAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


#################################################################################################
###
###  other tables
###
#################################################################################################
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
def add_column_other_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.otherAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@operation_wrapper
def add_column_products_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.productsAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@operation_wrapper
def create_schema_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.schemaCreate)
        conn.commit()


@operation_wrapper
def get_schema_changes(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(queries.schemaAll).fetchall()
        return set(list(map(lambda x: x[0], data)))


@operation_wrapper
def add_flag_schema(flag, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            data = cur.execute(queries.schemaInsert, [flag, 1])
            conn.commit()
        except sqlite3.IntegrityError as e:
            log.debug("Error: Unique constraint on schema flags violation occurred", e)
            # You can choose to retry the insert with a modified flag value or take other actions
            pass


@operation_wrapper
def get_all_others_transition(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(queries.othersALLTransition).fetchall()
        return data


@operation_wrapper
def drop_others_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.othersDrop)
        conn.commit()


@operation_wrapper
def write_others_table_transition(
    insertData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.othersInsert, insertData)
        conn.commit()


@operation_wrapper
def get_all_products_transition(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(queries.productsALLTransition).fetchall()
        return data


@operation_wrapper
def drop_products_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.productsDrop)
        conn.commit()


@operation_wrapper
def write_products_table_transition(
    insertData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.productsInsert, insertData)
        conn.commit()


@operation_wrapper
def write_models_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.modelDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(queries.modelInsert, [model_id])
            conn.commit()


#################################################################################################
###
###  helpers
###
#################################################################################################
def converthelper(media):
    if isinstance(media, list):
        return media
    elif isinstance(media, filter):
        return list(filter)
    else:
        return [media]


def create_tables(model_id, username):
    create_models_table(model_id=model_id, username=username)
    create_profile_table(model_id=model_id, username=username)
    create_post_table(model_id=model_id, username=username)
    create_message_table(model_id=model_id, username=username)
    create_media_table(model_id=model_id, username=username)
    create_products_table(model_id=model_id, username=username)
    create_others_table(model_id=model_id, username=username)
    create_stories_table(model_id=model_id, username=username)
    create_labels_table(model_id=model_id, username=username)
    create_schema_table(model_id=model_id, username=username)
    # modifications for current tables


def modify_tables(model_id=None, username=None):
    add_column_tables(model_id=model_id, username=username)
    modify_tables_constraints_and_columns(model_id=model_id, username=username)
    print("")


def add_column_tables(model_id=None, username=None):
    changes = get_schema_changes(model_id=model_id, username=username)
    if not "media_hash" in changes:
        add_column_media_hash(model_id=model_id, username=username)
        add_flag_schema("media_hash", model_id=model_id, username=username)
    if not "media_model_id" in changes:
        add_column_media_ID(model_id=model_id, username=username)
        add_flag_schema("media_model_id", model_id=model_id, username=username)
    if not "posts_model_id" in changes:
        add_column_post_ID(model_id=model_id, username=username)
        add_flag_schema("posts_model_id", model_id=model_id, username=username)
    if not "products_model_id" in changes:
        add_column_products_ID(model_id=model_id, username=username)
        add_flag_schema("products_model_id", model_id=model_id, username=username)
    if not "other_model_id" in changes:
        add_column_other_ID(model_id=model_id, username=username)
        add_flag_schema("other_model_id", model_id=model_id, username=username)
    if not "stories_model_id" in changes:
        add_column_stories_ID(model_id=model_id, username=username)
        add_flag_schema("stories_model_id", model_id=model_id, username=username)
    if not "messages_model_id" in changes:
        add_column_messages_ID(model_id=model_id, username=username)
        add_flag_schema("messages_model_id", model_id=model_id, username=username)
    if not "labels_model_id" in changes:
        add_column_labels_ID(model_id=model_id, username=username)
        add_flag_schema("labels_model_id", model_id=model_id, username=username)


def modify_tables_constraints_and_columns(model_id=None, username=None):
    changes = get_schema_changes(model_id=model_id, username=username)
    if not "profile_username_constraint_removed" in changes:
        remove_unique_constriant_profile(model_id=model_id, username=username)
        add_flag_schema(
            "profile_username_constraint_removed", model_id=model_id, username=username
        )
    if not "stories_model_id_constraint_added" in changes:
        modify_unique_constriant_stories(model_id=model_id, username=username)
        add_flag_schema(
            "stories_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "media_model_id_constraint_added" in changes:
        modify_unique_constriant_media(model_id=model_id, username=username)
        add_flag_schema(
            "media_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "posts_model_id_constraint_added" in changes:
        modify_unique_constriant_posts(model_id=model_id, username=username)
        add_flag_schema(
            "posts_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "others_model_id_constraint_added" in changes:
        modify_unique_constriant_others(model_id=model_id, username=username)
        add_flag_schema(
            "others_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "products_model_id_constraint_added" in changes:
        modify_unique_constriant_products(model_id=model_id, username=username)
        add_flag_schema(
            "products_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "messages_model_id_constraint_added" in changes:
        modify_unique_constriant_messages(model_id=model_id, username=username)
        add_flag_schema(
            "messages_model_id_constraint_added", model_id=model_id, username=username
        )

    if not "labels_model_id_constraint_added" in changes:
        modify_unique_constriant_labels(model_id=model_id, username=username)
        add_flag_schema(
            "labels_model_id_constraint_added", model_id=model_id, username=username
        )


def create_backup(model_id, username):
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )

    now = arrow.now().float_timestamp
    last = cache.get(f"{username}_{model_id}_db_backup", default=now)
    if now - last > constants.getattr("DBINTERVAL") and database_path.exists():
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    elif (
        not pathlib.Path(database_path.parent / "backup").exists()
        or len(list(pathlib.Path(database_path.parent / "backup").iterdir())) == 0
    ):
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    cache.close()


def table_init_create(model_id=None, username=None):
    create_tables(model_id=model_id, username=username)
    create_backup(model_id, username)
    modify_tables(model_id, username)
    write_profile_table(model_id=model_id, username=username)
    write_models_table(model_id=model_id, username=username)


def make_messages_table_changes(all_messages, model_id=None, username=None):
    curr_id = set(get_all_messages_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_messages))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_messages))
    if len(new_posts) > 0:
        new_posts = converthelper(new_posts)
        write_messages_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = converthelper(curr_posts)
        update_messages_table(curr_posts, model_id=model_id, username=username)


def get_last_message_date(model_id=None, username=None):
    data = get_messages_progress_data(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x.get("date"))[-1].get("date")


def make_post_table_changes(all_posts, model_id=None, username=None):
    curr_id = get_all_post_ids(model_id=model_id, username=username)
    new_posts = list(filter(lambda x: x.id not in curr_id, all_posts))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_posts))
    if len(new_posts) > 0:
        new_posts = converthelper(new_posts)
        write_post_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = converthelper(curr_posts)
        update_posts_table(curr_posts, model_id=model_id, username=username)


def make_stories_tables_changes(
    all_stories: dict, model_id=None, username=None, conn=None
):
    curr_id = set(get_all_stories_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_stories))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_stories))
    if len(new_posts) > 0:
        new_posts = converthelper(new_posts)
        write_stories_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = converthelper(curr_posts)
        update_stories_table(curr_posts, model_id=model_id, username=username)


def update_media_table_via_api_helper(
    media, model_id=None, conn=None, **kwargs
) -> list:
    insertData = [
        media.id,
        media.postid,
        media.url,
        media.responsetype.capitalize(),
        media.mediatype.capitalize(),
        media.preview,
        media.linked,
        media.date,
        media.id,
        model_id,
    ]
    conn.execute(queries.mediaUpdateAPI, insertData)


def update_media_table_download_helper(
    media, filename=None, hashdata=None, conn=None, downloaded=None, **kwargs
) -> list:
    prevData = conn.execute(queries.mediaDupeCheck, (media.id,)).fetchall()
    prevData = prevData[0] if isinstance(prevData, list) and bool(prevData) else None
    insertData = media_exist_insert_helper(
        filename=filename, hashdata=hashdata, prevData=prevData, downloaded=downloaded
    )
    insertData.append(media.id)
    conn.execute(queries.mediaUpdateDownload, insertData)


def media_exist_insert_helper(
    filename=None, downloaded=None, hashdata=None, prevData=None
):
    directory = None
    filename_path = None
    size = None
    if filename and pathlib.Path(filename).exists():
        directory = str(pathlib.Path(filename).parent)
        filename_path = str(pathlib.Path(filename).name)
        size = math.ceil(pathlib.Path(filename).stat().st_size)
    elif filename:
        directory = str(pathlib.Path(filename).parent)
        filename_path = str(pathlib.Path(filename).name)
    elif prevData:
        directory = prevData[3]
        filename_path = prevData[4]
        size = prevData[5]
        hashdata = prevData[13] or hashdata
    insertData = [
        directory,
        filename_path,
        size,
        downloaded,
        hashdata,
    ]
    return insertData


async def batch_mediainsert(media, **kwargs):
    curr = set(get_media_ids(**kwargs) or [])
    mediaDict = {}
    for ele in media:
        mediaDict[ele.id] = ele
    await write_media_table_via_api_batch(
        list(filter(lambda x: x.id not in curr, mediaDict.values())), **kwargs
    )


def remove_unique_constriant_profile(model_id=None, username=None):
    data = get_all_profiles(model_id=model_id, username=username)
    drop_profiles_table(model_id=model_id, username=username)
    create_profile_table(model_id=model_id, username=username)
    write_profile_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_stories(model_id=None, username=None):
    data = get_all_stories_transition(model_id=model_id, username=username)
    drop_stories_table(model_id=model_id, username=username)
    create_stories_table(model_id=model_id, username=username)
    write_stories_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_media(model_id=None, username=None):
    data = get_all_medias_transition(model_id=model_id, username=username)
    drop_media_table(model_id=model_id, username=username)
    create_media_table(model_id=model_id, username=username)
    write_media_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_posts(model_id=None, username=None):
    data = get_all_posts_transition(model_id=model_id, username=username)
    drop_posts_table(model_id=model_id, username=username)
    create_post_table(model_id=model_id, username=username)
    write_post_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_others(model_id=None, username=None):
    data = get_all_others_transition(model_id=model_id, username=username)
    drop_others_table(model_id=model_id, username=username)
    create_others_table(model_id=model_id, username=username)
    write_others_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_products(model_id=None, username=None):
    data = get_all_products_transition(model_id=model_id, username=username)
    drop_products_table(model_id=model_id, username=username)
    create_products_table(model_id=model_id, username=username)
    write_products_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_messages(model_id=None, username=None):
    data = get_all_messages_transition(model_id=model_id, username=username)
    drop_messages_table(model_id=model_id, username=username)
    create_message_table(model_id=model_id, username=username)
    write_messages_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_labels(model_id=None, username=None):
    data = get_all_labels_transition(model_id=model_id, username=username)
    drop_labels_table(model_id=model_id, username=username)
    create_labels_table(model_id=model_id, username=username)
    write_labels_table_transition(data, model_id=model_id, username=username)
