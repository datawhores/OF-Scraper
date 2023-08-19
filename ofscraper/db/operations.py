r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
from collections import abc
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import singledispatch,partial
import asyncio
import contextlib
import pathlib
import sqlite3
import aiosqlite
import math
import logging
from filelock import FileLock
from rich.console import Console
from ..db import queries
from ..utils.paths import createDir,getDB
import ofscraper.classes.placeholder as placeholder
from ofscraper.constants import DATABASE_TIMEOUT

console=Console()
log=logging.getLogger("shared")
#print error 
PROCESS_POOL=ThreadPoolExecutor(max_workers=1)


def operation_wrapper_async(func:abc.Callable):

    async def inner(*args,**kwargs): 
            LOCK_POOL=ThreadPoolExecutor(max_workers=1)
            lock=FileLock(getDB(),timeout=-1)
            loop = asyncio.get_event_loop()
            try: 
                await loop.run_in_executor(LOCK_POOL, lock.acquire)
                datebase_path =placeholder.Placeholders().databasePathHelper(kwargs.get("model_id"),kwargs.get("username"))
                createDir(datebase_path.parent)
                conn=sqlite3.connect(datebase_path,check_same_thread=False,timeout=10)
                await loop.run_in_executor(PROCESS_POOL, partial(func,*args,**kwargs,conn=conn))
            except sqlite3.OperationalError as E:
                log.info("DB may be locked") 
                raise E  
            except Exception as E:
                raise E   
            finally:
                await loop.run_in_executor(LOCK_POOL, partial(lock.release,force=True))
                log.trace("Force Closing DB") 
                conn.close()
    return inner


def operation_wrapper(func:abc.Callable):
    def inner(*args,**kwargs): 
            lock=FileLock(getDB())
            try:
                lock.acquire(timeout=-1)  
                datebase_path =placeholder.Placeholders().databasePathHelper(kwargs.get("model_id"),kwargs.get("username"))
                createDir(datebase_path.parent)
                conn=sqlite3.connect(datebase_path,check_same_thread=True,timeout=10)
                func(*args,**kwargs,conn=conn) 
            except sqlite3.OperationalError as E:
                log.info("DB may be locked") 
                raise E  
            except Exception as E:
                raise E   
            finally:
                lock.release(force=True)
                log.trace("Force Closing DB") 
                conn.close()
    return inner

@operation_wrapper
def create_message_table(model_id=None,username=None,conn=None):
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesCreate)
        conn.commit()

def write_messages_table(message: dict):
    @operation_wrapper
    def inner(model_id=None,username=None,message=None,conn=None):
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.messageDupeCheck,(message.id,)).fetchall())==0:
                insertData=(message.id,message.text,message.price,message.paid,message.archived,message.date,message.model_id)
                cur.execute(queries.messagesInsert,insertData)
                conn.commit()
    return inner(model_id=message.model_id,username=message.username,message=message)



            
  
@operation_wrapper
def write_post_table(data: dict, model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.postDupeCheck,(data.id,)).fetchall())==0:
            insertData=(data.id,data.text,data.price,data.paid ,data.archived,data.date)
            cur.execute(queries.postInsert,insertData)
            conn.commit()
@operation_wrapper
def create_post_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postCreate)
        conn.commit()
@operation_wrapper
def create_stories_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.storiesCreate)
        conn.commit()
@operation_wrapper
def write_stories_table(data: dict,model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.storiesDupeCheck,(data.id,)).fetchall())==0:
            insertData=(data.id,data.text or data.title or "",data.price,data.paid ,data.archived,data.date)
            cur.execute(queries.storiesInsert,insertData)
            conn.commit()
@operation_wrapper
def create_media_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaCreate)
        conn.commit()
@operation_wrapper
def get_media_ids(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allIDCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))
@operation_wrapper
def get_post_ids(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allPOSTCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))

@operation_wrapper
def get_profile_info(model_id=None,username=None,conn=None) -> list:
    datebase_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    if not pathlib.Path(datebase_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        modelinfo=cur.execute(queries.profileDupeCheck,(model_id,)).fetchall() or [(None,)]
        conn.commit()
        return modelinfo[0][-1]


@operation_wrapper_async
def write_media_table(media,filename,model_id=None,username=None,conn=None) -> list:  
        insertData=[media.id,media.postid,media.url,str(pathlib.Path(filename).parent),pathlib.Path(filename).name,
        math.ceil(pathlib.Path(filename).stat().st_size),media.responsetype_.capitalize(),media.mediatype.capitalize() ,
        media.preview,media.linked, 1,media.date]
        # if len( (await conn.execute(queries.mediaDupeCheck,(media.id,)).fetchall())==0:
        if len(conn.execute(queries.mediaDupeCheck,(media.id,)).fetchall())==0:
            conn.execute(queries.mediaInsert,insertData)
        else:
            insertData.append(media.id)
            conn.execute(queries.mediaUpdate,insertData)
        conn.commit()
        


   
   
@operation_wrapper
def create_products_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.productCreate)
        conn.commit()
@operation_wrapper
def create_others_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.otherCreate)
        conn.commit()
@operation_wrapper
def create_profile_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.profilesCreate)
        conn.commit()

@operation_wrapper
def write_profile_table(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData=[model_id,username]
        if len(cur.execute(queries.profileDupeCheck,(model_id,)).fetchall())==0:
            cur.execute(queries.profileInsert,insertData)
        else:
            insertData.append(model_id)
            cur.execute(queries.profileUpdate,insertData)
        conn.commit()

@operation_wrapper
def create_labels_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.labelsCreate)
        conn.commit()

@operation_wrapper
def write_labels_table(label: dict, model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        for post in label.posts:
            if len(cur.execute(queries.labelDupeCheck,(label.label_id, post.id)).fetchall())==0:
                insertData=(label.label_id, label.name,label.type, post.id)
                cur.execute(queries.labelInsert,insertData)
                conn.commit()


def create_tables(model_id,username):
    create_post_table(model_id=model_id,username=username)
    create_message_table(model_id=model_id,username=username)
    create_media_table(model_id=model_id,username=username)
    create_products_table(model_id=model_id,username=username)
    create_others_table(model_id=model_id,username=username)
    create_profile_table(model_id=model_id,username=username)
    create_stories_table(model_id=model_id,username=username)
    create_labels_table(model_id=model_id,username=username)

