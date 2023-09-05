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
from functools import partial
import asyncio
import contextlib
import pathlib
import sqlite3
import aiosqlite
import math
import logging
from filelock import FileLock
import arrow

from rich.console import Console
from diskcache import Cache
from ..db import queries
from ..utils.paths import createDir,getDB,getcachepath
import ofscraper.utils.config as config
import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.exit as exit
from ofscraper.constants import DBINTERVAL


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
                database_path =placeholder.Placeholders().databasePathHelper(kwargs.get("model_id"),kwargs.get("username"))
                createDir(database_path.parent)
                conn=sqlite3.connect(database_path,check_same_thread=False,timeout=10)
                return await loop.run_in_executor(PROCESS_POOL, partial(func,*args,**kwargs,conn=conn))
            except sqlite3.OperationalError as E:
                log.info("DB may be locked") 
                raise E 
            except KeyboardInterrupt as E:
                with exit.DelayedKeyboardInterrupt():
                    try:lock.release(True)
                    except:None
                    try:conn.close()
                    except:None
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
                database_path =placeholder.Placeholders().databasePathHelper(kwargs.get("model_id"),kwargs.get("username"))                
                createDir(database_path.parent)
                conn=sqlite3.connect(database_path,check_same_thread=True,timeout=10)
                return func(*args,**kwargs,conn=conn) 
            except sqlite3.OperationalError as E:
                log.info("DB may be locked") 
                raise E  
            except KeyboardInterrupt as E:
                with exit.DelayedKeyboardInterrupt():
                    try:lock.release(force=True)
                    except:None
                    try:conn.close()
                    except:None
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

def write_messages_table(messages: dict,**kwargs):
    @operation_wrapper  
    def inner(messages=None,conn=None,**kwargs):
        with contextlib.closing(conn.cursor()) as cur:
            messages=converthelper(messages)
            if len(messages)==0:return
            insertData=list(map(lambda message:(message.id,message.text,message.price,message.paid,message.archived,message.date,message.model_id),messages))
            cur.executemany(queries.messagesInsert,insertData)
            conn.commit()
    return inner(messages=messages,**kwargs)

@operation_wrapper
def get_all_messages_ids(model_id=None,username=None,conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allMessagesCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))


            
@operation_wrapper
def write_post_table(posts: list, model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        posts=converthelper(posts)
        if len(posts)==0:return
        insertData=list(map(lambda data:(data.id,data.text,data.price,data.paid ,data.archived,data.date),posts))
        cur.executemany(queries.postInsert,insertData)
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
def write_stories_table(stories: dict,model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        stories=converthelper(stories)
        insertData=list(map(lambda data:(data.id,data.text or data.title or "",data.price,data.paid ,data.archived,data.date),stories))
        cur.executemany(queries.storiesInsert,insertData)
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
        cur.execute(queries.allIDCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))

@operation_wrapper
def get_media_ids_downloaded(model_id=None,username=None,conn=None,**kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allDLIDCheck)
        conn.commit()
        return list(map(lambda x:x[0],cur.fetchall()))

@operation_wrapper
def get_profile_info(model_id=None,username=None,conn=None) -> list:
    database_path =placeholder.Placeholders().databasePathHelper(model_id,username)
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
def write_media_table(medias,filename=None,conn=None,downloaded=False,**kwargs) -> list:
        medias=converthelper(medias)
        if len(medias)==0:return
        insertData=list(map(lambda media:[media.id,media.postid,media.url,str(pathlib.Path(filename).parent) if filename else filename,pathlib.Path(filename).name if filename else filename,
        math.ceil(pathlib.Path(filename).stat().st_size  )if filename else filename,media.responsetype_.capitalize(),media.mediatype.capitalize() ,
        media.preview,media.linked, 1 if downloaded else 0,media.date],medias))
        conn.executemany(queries.mediaInsert,insertData)
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
    mediaDict={}
    for ele in media:mediaDict[ele.id]=ele
    await funct(list(filter(lambda x:x.id not in curr,mediaDict.values())),**kwargs)
  

 
 

@operation_wrapper_async
def update_response_media_table(medias,conn=None,downloaded=False,**kwargs) -> list:
    medias=converthelper(medias)
    insertData=list(map(lambda media:[media.responsetype_.capitalize(),media.mediatype.capitalize(),media.id],medias))
    conn.executemany(queries.mediaTypeUpdate,insertData)
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
def write_labels_table(label:dict, posts:dict,model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as curr:
        insertData=list(map(lambda post:(label.label_id, label.name,label.type, post.id),posts))     
        curr.executemany(queries.labelInsert,insertData)
        conn.commit()


@operation_wrapper
def get_all_labels_ids(model_id=None,username=None,conn=None):
    with contextlib.closing(conn.cursor()) as curr:
        curr.execute(queries.labelID)
        conn.commit()
        return curr.fetchall()



def converthelper(media):
    if isinstance(media,list):
        return media
    elif isinstance(media,filter):
       return list(filter)
    else:
        return [media]



def create_tables(model_id,username):
    create_post_table(model_id=model_id,username=username)
    create_message_table(model_id=model_id,username=username)
    create_media_table(model_id=model_id,username=username)
    create_products_table(model_id=model_id,username=username)
    create_others_table(model_id=model_id,username=username)
    create_profile_table(model_id=model_id,username=username)
    create_stories_table(model_id=model_id,username=username)
    create_labels_table(model_id=model_id,username=username)


def create_backup(model_id,username):
    database_path =placeholder.Placeholders().databasePathHelper(model_id,username)
    cache = Cache(getcachepath(),disk=config.get_cache_mode(config.read_config()))

    now=arrow.now().float_timestamp
    last=cache.get(f"{username}_{model_id}_db_backup",now)
    if now-last>DBINTERVAL and database_path.exists():
        database_copy=placeholder.Placeholders().databasePathCopyHelper(model_id,username)
        createDir(database_copy.parent)
        shutil.copy2(database_path,database_copy)
        cache.set(f"{username}_{model_id}_db_backup",now)
    elif not pathlib.Path(database_path.parent/"backup").exists() or len(list(pathlib.Path(database_path.parent/"backup").iterdir()))==0:
        database_copy=placeholder.Placeholders().databasePathCopyHelper(model_id,username)
        createDir(database_copy.parent)
        shutil.copy2(database_path,database_copy)
        cache.set(f"{username}_{model_id}_db_backup",now)
    cache.close()


                    
    

