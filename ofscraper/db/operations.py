r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
from collections import abc
from concurrent.futures import ThreadPoolExecutor
import shutil
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



def operation_wrapper_async(func:abc.Callable):

    async def inner(*args,**kwargs): 
            try:
                LOCK_POOL=ThreadPoolExecutor(max_workers=1)
                PROCESS_POOL=ThreadPoolExecutor(max_workers=1)
                lock=FileLock(getDB(),timeout=-1)
                loop = asyncio.get_event_loop()
            except Exception as E:
                raise E
            
            try: 
                await loop.run_in_executor(LOCK_POOL, lock.acquire)
                datebase_path =placeholder.Placeholders().databasePathHelper(kwargs.get("model_id"),kwargs.get("username"))
                database_copy=placeholder.Placeholders().databasePathCopyHelper(kwargs.get("model_id"),kwargs.get("username"))
                createDir(datebase_path.parent)
                if datebase_path.exists() and not database_copy.exists():
                    shutil.copy(datebase_path,database_copy)
                conn=sqlite3.connect(datebase_path,check_same_thread=False,timeout=10)
                return await loop.run_in_executor(PROCESS_POOL, partial(func,*args,**kwargs,conn=conn))
            except sqlite3.OperationalError as E:
                log.info("DB may be locked") 
                raise E  
            except Exception as E:
                raise E   
            finally:
                conn.close()
                await loop.run_in_executor(LOCK_POOL, partial(lock.release,force=True))
                log.trace("Force Closing DB") 
                
    return inner


def operation_wrapper(func:abc.Callable):
    def inner(*args,**kwargs):
            try:
                lock=FileLock(getDB(),timeout=-1)
            except Exception as E:
                raise E
            try:
                lock.acquire(timeout=-1)  
                datebase_path =placeholder.Placeholders().databasePathHelper(kwargs.get("model_id"),kwargs.get("username"))
                database_copy=placeholder.Placeholders().databasePathCopyHelper(kwargs.get("model_id"),kwargs.get("username"))
                
                createDir(datebase_path.parent)
                if datebase_path.exists() and not database_copy.exists():
                    shutil.copy(datebase_path,database_copy)                                
                conn=sqlite3.connect(datebase_path,check_same_thread=True,timeout=10)
                return func(*args,**kwargs,conn=conn) 
            except sqlite3.OperationalError as E:
                log.info("DB may be locked") 
                raise E  
            except Exception as E:
                raise E   
            finally:
                conn.close()
                lock.release(force=True)
                log.trace("Force Closing DB") 
               
    return inner

@operation_wrapper
def create_message_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.messagesCreate)
        conn.commit()

def write_messages_table(message: dict,**kwargs):
    @operation_wrapper
    def inner(model_id=None,username=None,message=None,conn=None):
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.messageDupeCheck,(message.id,)).fetchall())==0:
                insertData=(message.id,message.text,message.price,message.paid,message.archived,message.date,message.model_id)
                cur.execute(queries.messagesInsert,insertData)
                conn.commit()
    return inner(message=message,**kwargs)

@operation_wrapper
def get_all_messages_ids(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allMessagesCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))


            
  
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
def get_all_post_ids(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allPOSTCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))

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
def get_all_stories_ids(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allStoriesCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))

@operation_wrapper
def create_media_table(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.mediaCreate)
        conn.commit()
@operation_wrapper
def get_media_ids(model_id=None,username=None,conn=None,**kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allDLIDCheck)
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
def update_media_table(media,filename=None,conn=None,downloaded=False,**kwargs) -> list:  
        insertData=[media.id,media.postid,media.url,str(pathlib.Path(filename).parent) if filename else filename,pathlib.Path(filename).name if filename else filename,
        math.ceil(pathlib.Path(filename).stat().st_size  )if filename else filename,media.responsetype_.capitalize(),media.mediatype.capitalize() ,
        media.preview,media.linked, 1 if downloaded else 0,media.date]
        # if len( (await conn.execute(queries.mediaDupeCheck,(media.id,)).fetchall())==0:
        if len(conn.execute(queries.mediaDupeCheck,(media.id,)).fetchall())==0:
            conn.execute(queries.mediaInsert,insertData)
        else:
            insertData.append(media.id)
            conn.execute(queries.mediaUpdate,insertData)
        conn.commit()


@operation_wrapper_async
def write_media_table(media,filename=None,conn=None,downloaded=False,**kwargs) -> list:  
        if len(conn.execute(queries.mediaDupeCheck,(media.id,)).fetchall())==0:
            insertData=[media.id,media.postid,media.url,str(pathlib.Path(filename).parent) if filename else filename,pathlib.Path(filename).name if filename else filename,
            math.ceil(pathlib.Path(filename).stat().st_size  )if filename else filename,media.responsetype_.capitalize(),media.mediatype.capitalize() ,
            media.preview,media.linked, 1 if downloaded else 0,media.date]
            conn.execute(queries.mediaInsert,insertData)
        conn.commit()
   
@operation_wrapper
def get_timeline_media(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getTimelineMedia)
        data=list(map(lambda x:x,cur.fetchall()))
        conn.commit()
        return data
    
@operation_wrapper
def get_archived_media(conn=None,**kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getArchivedMedia)
        data=list(map(lambda x:x,cur.fetchall()))
        conn.commit()
        return data

@operation_wrapper
def get_messages_media(conn=None,**kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.getMessagesMedia)
        data=list(map(lambda x:x,cur.fetchall()))
        conn.commit()
        return data
async def batch_mediainsert(media,funct,**kwargs):
    curr=set(get_media_ids(**kwargs) or [])

    tasks=[asyncio.create_task(funct(ele,**kwargs)) for ele in filter(lambda x:x.id not in curr,media) ]
    [await ele for ele in tasks] 
 
 

@operation_wrapper_async
def update_response_media_table(media,conn=None,downloaded=False,**kwargs) -> list:  
    insertData=[media.responsetype_.capitalize(),media.mediatype.capitalize(),media.id]
    conn.execute(queries.mediaTypeUpdate,insertData)
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

