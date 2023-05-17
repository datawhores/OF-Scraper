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
import math
from rich.console import Console
from ..db import queries
from ..utils.paths import createDir,databasePathHelper

console=Console()

def create_message_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.messagesCreate)
            conn.commit()


def write_messages_table(message: dict):
    datebase_path =databasePathHelper(message.model_id,message.username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.messageDupeCheck,(message.id,)).fetchall())==0:
                insertData=(message.id,message.text,message.price,message.paid,message.archived,message.date,message.model_id)
                cur.execute(queries.messagesInsert,insertData)
                conn.commit()



            
  

def write_post_table(data: dict, model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.postDupeCheck,(data.id,)).fetchall())==0:
                insertData=(data.id,data.text,data.price,data.paid ,data.archived,data.date)
                cur.execute(queries.postInsert,insertData)
                conn.commit()

def create_post_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.postCreate)
            conn.commit()

def create_stories_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.storiesCreate)
            conn.commit()
def write_stories_table(data: dict, model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.storiesDupeCheck,(data.id,)).fetchall())==0:
                insertData=(data.id,data.text or data.title or "",data.price,data.paid ,data.archived,data.date)
                cur.execute(queries.storiesInsert,insertData)
                conn.commit()

def create_media_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.mediaCreate)
            conn.commit()

def get_media_ids(model_id,username) -> list:
    datebase_path =databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.allIDCheck)
            conn.commit()
            return list(map(lambda x:x[0],cur.fetchall()))
def write_media_table(media,filename,model_id,username) -> list:
    datebase_path =databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            insertData=[media.id,media.postid,media.url,str(pathlib.Path(filename).parent),pathlib.Path(filename).name,
            math.ceil(pathlib.Path(filename).stat().st_size),media.responsetype_.capitalize(),media.mediatype.capitalize() ,
            media.preview,media.linked, 1,media.date]
            if len(cur.execute(queries.mediaDupeCheck,(media.id,)).fetchall())==0:
                cur.execute(queries.mediaInsert,insertData)
            else:
                insertData.append(media.id)
                cur.execute(queries.mediaUpdate,insertData)
            conn.commit()
   

def create_products_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.productCreate)
            conn.commit()
def create_others_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.otherCreate)
            conn.commit()

def create_profile_table(model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.profilesCreate)
            conn.commit()


def write_profile_table(model_id,username) -> list:
    datebase_path =databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            insertData=[model_id,username]
            if len(cur.execute(queries.profileDupeCheck,(model_id,)).fetchall())==0:
                cur.execute(queries.profileInsert,insertData)
            else:
                insertData.append(model_id)
                cur.execute(queries.profileUpdate,insertData)
            conn.commit()
   
