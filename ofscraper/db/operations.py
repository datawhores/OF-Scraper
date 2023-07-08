r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import contextlib
import pathlib
import sqlite3
import aiosqlite
import traceback
import math
import logging
from rich.console import Console
from ..db import queries
from ..utils.paths import createDir
import ofscraper.classes.placeholder as placeholder

console=Console()
log=logging.getLogger(__package__)
#print error 
def operation_wrapper(func): 
    def inner(*args,**kwargs): 
        try:
            return func(*args,**kwargs) 
        except sqlite3.OperationalError as E:
            log.info("DB may be locked") 
            raise E    
    return inner



@operation_wrapper
def create_message_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.messagesCreate)
            conn.commit()

@operation_wrapper
def write_messages_table(message: dict):
    datebase_path =placeholder.Placeholders().databasePathHelper(message.model_id,message.username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.messageDupeCheck,(message.id,)).fetchall())==0:
                insertData=(message.id,message.text,message.price,message.paid,message.archived,message.date,message.model_id)
                cur.execute(queries.messagesInsert,insertData)
                conn.commit()



            
  
@operation_wrapper
def write_post_table(data: dict, model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.postDupeCheck,(data.id,)).fetchall())==0:
                insertData=(data.id,data.text,data.price,data.paid ,data.archived,data.date)
                cur.execute(queries.postInsert,insertData)
                conn.commit()
@operation_wrapper
def create_post_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.postCreate)
            conn.commit()
@operation_wrapper
def create_stories_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.storiesCreate)
            conn.commit()
@operation_wrapper
def write_stories_table(data: dict, model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.storiesDupeCheck,(data.id,)).fetchall())==0:
                insertData=(data.id,data.text or data.title or "",data.price,data.paid ,data.archived,data.date)
                cur.execute(queries.storiesInsert,insertData)
                conn.commit()
@operation_wrapper
def create_media_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.mediaCreate)
            conn.commit()
@operation_wrapper
def get_media_ids(model_id,username) -> list:
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.allIDCheck)
            conn.commit()
            return list(map(lambda x:x[0],cur.fetchall()))
@operation_wrapper
def get_post_ids(model_id,username) -> list:
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.allPOSTCheck)
            conn.commit()
            return list(map(lambda x:x[0],cur.fetchall()))

@operation_wrapper
def get_profile_info(model_id,username) -> list:
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    if not pathlib.Path(datebase_path).exists():
        return None
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            modelinfo=cur.execute(queries.prorfileDupeCheck,(model_id,)).fetchall() or [(None,)]
            conn.commit()
            return modelinfo[0][-1]


@operation_wrapper
async def write_media_table(media,filename,model_id,username) -> list:
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    async with aiosqlite.connect(datebase_path) as conn:
        insertData=[media.id,media.postid,media.url,str(pathlib.Path(filename).parent),pathlib.Path(filename).name,
        math.ceil(pathlib.Path(filename).stat().st_size),media.responsetype_.capitalize(),media.mediatype.capitalize() ,
        media.preview,media.linked, 1,media.date]
        if len((await (await conn.execute(queries.mediaDupeCheck,(media.id,))).fetchall()))==0:
            await conn.execute(queries.mediaInsert,insertData)
        else:
            insertData.append(media.id)
            await conn.execute(queries.mediaUpdate,insertData)
        await conn.commit()


   
   
@operation_wrapper
def create_products_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.productCreate)
            conn.commit()
@operation_wrapper
def create_others_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.otherCreate)
            conn.commit()
@operation_wrapper
def create_profile_table(model_id,username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.profilesCreate)
            conn.commit()

@operation_wrapper
def write_profile_table(model_id,username) -> list:
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            insertData=[model_id,username]
            if len(cur.execute(queries.profileDupeCheck,(model_id,)).fetchall())==0:
                cur.execute(queries.profileInsert,insertData)
            else:
                insertData.append(model_id)
                cur.execute(queries.profileUpdate,insertData)
            conn.commit()

@operation_wrapper
def create_labels_table(model_id, username):
    datebase_path = placeholder.Placeholders().databasePathHelper(model_id, username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path, check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.labelsCreate)
            conn.commit()

@operation_wrapper
def write_labels_table(label: dict, model_id, username):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id, username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            for post in label.posts:
                if len(cur.execute(queries.labelDupeCheck,(label.label_id, post.id)).fetchall())==0:
                    insertData=(label.label_id, label.name,label.type, post.id)
                    cur.execute(queries.labelInsert,insertData)
                    conn.commit()


def create_tables(model_id,username):
    create_post_table(model_id,username)
    create_message_table(model_id,username)
    create_media_table(model_id,username)
    create_products_table(model_id,username)
    create_others_table(model_id,username)
    create_profile_table(model_id,username)
    create_stories_table(model_id,username)
    create_labels_table(model_id, username)
