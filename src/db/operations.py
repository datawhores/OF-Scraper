r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import contextlib
import glob
import pathlib
import sqlite3
import json
import math
from itertools import chain
from hashlib import md5
from rich.console import Console
console=Console()
from ..constants import configPath
from ..utils import separate, profiles
from ..db import queries
from ..utils.paths import createDir,databasePathHelper,messageResponsePathHelper,timelineResponsePathHelper,\
archiveResponsePathHelper,pinnedResponsePathHelper

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

def save_messages_response(messages,model_id,username):
    messagepath =messageResponsePathHelper(model_id,username)
    createDir(messagepath.parent)
    with open(messagepath,"w") as p:
        p.write(json.dumps({"posts":messages}))

def read_messages_response(model_id,username):
    messagepath =messageResponsePathHelper(model_id,username)
    if pathlib.Path(messagepath).exists():
        with open(messagepath,"r") as p:
            messages=json.loads(p.read() or '{"posts": []}')["posts"]
        if len(messages)>0:
            return messages
    return []
            
  

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

def save_timeline_response(posts,model_id,username,):
    messagepath =timelineResponsePathHelper(model_id,username)
    createDir(messagepath.parent)
    with open(messagepath,"w") as p:	
        p.write(json.dumps({"posts":posts}))

def read_timeline_response(model_id,username):
    messagepath =timelineResponsePathHelper(model_id,username)
    if pathlib.Path(messagepath).exists():
        with open(messagepath,"r") as p:
            messages=json.loads(p.read() or '{"posts": []}')["posts"]
        if len(messages)>0:
            return messages
    return []
            
def save_archive_response(posts,model_id,username):
    messagepath =archiveResponsePathHelper(model_id,username)
    createDir(messagepath.parent)
    with open(messagepath,"w") as p:	
        p.write(json.dumps({"posts":posts}))

def read_archive_response(model_id,username):
    messagepath =archiveResponsePathHelper(model_id,username)
    if pathlib.Path(messagepath).exists():
        with open(messagepath,"r") as p:
            messages=json.loads(p.read() or '{"posts": []}')["posts"]
        if len(messages)>0:
            return messages
    return []
def save_pinned_response(posts,model_id,username):
    messagepath =pinnedResponsePathHelper(model_id,username)
    createDir(messagepath.parent)
    with open(messagepath,"w") as p:	
        p.write(json.dumps({"posts":posts}))           

def read_pinned_response(model_id,username):
    messagepath =pinnedResponsePathHelper(model_id,username)
    if pathlib.Path(messagepath).exists():
        with open(messagepath,"r") as p:
            messages=json.loads(p.read() or '{"posts": []}')["posts"]
        if len(messages)>0:
            return messages
    return []
            

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
   
# def read_foreign_profile_table(datebase_path):
#     with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
#         with contextlib.closing(conn.cursor()) as cur:
#             cur.execute(queries.profileData)
#             conn.commit()
#             return list(map(lambda x:x,cur.fetchall())) 

# def read_foreign_database(path) -> list:
#     database_files = glob.glob(path.strip('\'\"') + '/*.db')

#     database_results = []
#     for file in database_files:
#         with contextlib.closing(sqlite3.connect(file,check_same_thread=False)) as conn:
#             with contextlib.closing(conn.cursor()) as cur:
#                 read_sql = """SELECT media_id, filename FROM medias"""
#                 cur.execute(read_sql)
#                 for result in cur.fetchall():
#                     database_results.append(result)

#     return database_results





# def write_from_foreign_database(results: list, model_id):
#     profile = profiles.get_current_profile()
    

#     database_path = pathlib.Path.home() / configPath / profile / databaseFile

#     # Create the database table in case it doesn't exist:
#     create_database(model_id, database_path)

#     # Filter results to avoid adding duplicates to database:
#     media_ids = get_media_ids(model_id)
#     filtered_results = separate.separate_database_results_by_id(
#         results, media_ids)

#     # Insert results into our database:
#     with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
#         with contextlib.closing(conn.cursor()) as cur:
#             model_insert_sql = f"""
#             INSERT INTO '{model_id}'(
#                 media_id, filename
#             )
#             VALUES (?, ?);"""
#             cur.executemany(model_insert_sql, filtered_results)
#             conn.commit()

#     console.print(f'Migration complete. Migrated {len(filtered_results)} items.')




