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
import contextlib
import logging
import math
import pathlib
import sqlite3

from rich.console import Console

import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.queries as queries
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


@wrapper.operation_wrapper
def create_media_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaCreate)
        conn.commit()


@wrapper.operation_wrapper
def add_column_media_hash(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.mediaAddColumnHash)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: hash":
                raise E


@wrapper.operation_wrapper
def add_column_media_ID(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.mediaAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def get_media_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allIDCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper
def get_media_ids_downloaded(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allDLIDCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper
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


@wrapper.operation_wrapper
def get_dupe_media_files(
    model_id=None, username=None, conn=None, hash=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaDupeFiles, [hash])
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper_async
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
        update_media_table_via_api_helper(
            media, curr=curr, model_id=model_id, conn=conn
        )
        update_media_table_download_helper(
            media,
            filename=filename,
            hashdata=hashdata,
            conn=conn,
            curr=curr,
            downloaded=downloaded,
        )


@wrapper.operation_wrapper_async
def write_media_table_via_api_batch(medias, model_id=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(
                lambda media: [
                    media.id,
                    media.postid,
                    media.url or media.mpd,
                    media.responsetype.capitalize(),
                    media.mediatype.capitalize(),
                    media.preview,
                    media.linked,
                    media.date,
                    model_id,
                ],
                medias,
            )
        )

        curr.executemany(queries.mediaInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_media_table_transition(insertData, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as curr:
        insertData = [[*ele, model_id] for ele in insertData]
        curr.executemany(queries.mediaInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def get_all_medias_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaALLTransition)
        conn.commit()
        return cur.fetchall()


@wrapper.operation_wrapper
def drop_media_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaDrop)
        conn.commit()


@wrapper.operation_wrapper
def get_messages_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getMessagesMedia, [model_id])
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


@wrapper.operation_wrapper
def get_archived_media(conn=None, model_id=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getArchivedMedia, [model_id])
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


@wrapper.operation_wrapper
def get_timeline_media(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getTimelineMedia, [model_id])
        data = list(map(lambda x: x, cur.fetchall()))
        conn.commit()
        return data


def update_media_table_via_api_helper(
    media, model_id=None, conn=None, curr=None, **kwargs
) -> list:
    insertData = [
        media.id,
        media.postid,
        media.url or media.mpd,
        media.responsetype.capitalize(),
        media.mediatype.capitalize(),
        media.preview,
        media.date,
        model_id,
        media.id,
    ]
    curr.execute(queries.mediaUpdateAPI, insertData)
    conn.commit()


def update_media_table_download_helper(
    media, filename=None, hashdata=None, conn=None, downloaded=None, curr=None, **kwargs
) -> list:
    prevData = curr.execute(queries.mediaDupeCheck, (media.id,)).fetchall()
    prevData = prevData[0] if isinstance(prevData, list) and bool(prevData) else None
    insertData = media_exist_insert_helper(
        filename=filename, hashdata=hashdata, prevData=prevData, downloaded=downloaded
    )
    insertData.append(media.id)
    curr.execute(queries.mediaUpdateDownload, insertData)
    conn.commit()


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


def modify_unique_constriant_media(model_id=None, username=None):
    data = get_all_medias_transition(model_id=model_id, username=username)
    drop_media_table(model_id=model_id, username=username)
    create_media_table(model_id=model_id, username=username)
    write_media_table_transition(data, model_id=model_id, username=username)
