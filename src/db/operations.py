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
from itertools import chain
from hashlib import md5
from rich.console import Console
console=Console()
from ..constants import configPath
from ..utils import separate, profiles
from ..db import queries
from ..utils.paths import createDir,databasePathHelper,messageResponsePathHelper,timelineResponsePathHelper,\
archiveResponsePathHelper,pinnedResponsePathHelper




def write_messages_table(data: dict, model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.messageDupeCheck,(data['id'],)).fetchall())==0:
                insertData=(data["id"],data["text"],data.get('price') or 0,len(list(filter(lambda x:x['canView']==False,data['media'])))==0,0,data["createdAt"],model_id)
                cur.execute(queries.messagesInsert,insertData)
                conn.commit()

def save_messages_response(model_id,username,messages):
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
            
  
 # This is specifically for writing to db

def write_post_table(data: dict, model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.postDupeCheck,(data['id'],)).fetchall())==0:
                insertData=(data["id"],data["text"],data.get('price') or 0,data.get("isOpen") or data.get("isOpened") or len(list(filter(lambda x:x['canView']==False,data['media'])))==0 ,data["isArchived"],data["postedAt"])
                cur.execute(queries.postInsert,insertData)
                conn.commit()



def save_timeline_response(model_id,username,posts):
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
            
def save_archive_response(model_id,username,posts):
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
def save_pinned_response(model_id,username,posts):
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
            



def write_stories_table(data: dict, model_id,username):
    datebase_path =databasePathHelper(model_id,username)
    createDir(datebase_path.parent)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            if len(cur.execute(queries.storiesDupeCheck,(data['id'],)).fetchall())==0:
                insertData=(data["id"],data.get("text") or data.get("title") or "",0,1 ,0,data["createdAt"])
                cur.execute(queries.storiesInsert,insertData)
                conn.commit()

def get_media_ids(model_id,username) -> list:
    datebase_path =databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute(queries.allIDCheck)
            conn.commit()
            return cur.fetchall()
def write_media(data,model_id,username) -> list:
    datebase_path =databasePathHelper(model_id,username)
    with contextlib.closing(sqlite3.connect(datebase_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            insertData=(data["id"],data.get("text") or data.get("title") or "",0,1 ,0,data["createdAt"])
            cur.execute(queries.insertMedia,insertData)
            conn.commit()
            return cur.fetchall()
   



def read_foreign_database(path) -> list:
    database_files = glob.glob(path.strip('\'\"') + '/*.db')

    database_results = []
    for file in database_files:
        with contextlib.closing(sqlite3.connect(file,check_same_thread=False)) as conn:
            with contextlib.closing(conn.cursor()) as cur:
                read_sql = """SELECT media_id, filename FROM medias"""
                cur.execute(read_sql)
                for result in cur.fetchall():
                    database_results.append(result)

    return database_results


def write_from_foreign_database(results: list, model_id):
    profile = profiles.get_current_profile()
    

    database_path = pathlib.Path.home() / configPath / profile / databaseFile

    # Create the database table in case it doesn't exist:
    create_database(model_id, database_path)

    # Filter results to avoid adding duplicates to database:
    media_ids = get_media_ids(model_id)
    filtered_results = separate.separate_database_results_by_id(
        results, media_ids)

    # Insert results into our database:
    with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            model_insert_sql = f"""
            INSERT INTO '{model_id}'(
                media_id, filename
            )
            VALUES (?, ?);"""
            cur.executemany(model_insert_sql, filtered_results)
            conn.commit()

    console.print(f'Migration complete. Migrated {len(filtered_results)} items.')




def create_paid_database(model_id, path=None):
    profile = profiles.get_current_profile()
    path = path or pathlib.Path.home() / configPath / profile /"paid"/f"{model_id}.db"
    pathlib.Path(path).parent.mkdir(exist_ok=True,parents=True)
    with contextlib.closing(sqlite3.connect(check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            try:
                model_sql = f"""
                CREATE TABLE IF NOT EXISTS hashes (id integer PRIMARY KEY, hash int);"""
                cur.execute(model_sql)
            except sqlite3.OperationalError:
                pass

def get_paid_media_ids(model_id) -> list:
    profile = profiles.get_current_profile()

    database_path = path or pathlib.Path.home() / configPath / profile /"paid"/f"{model_id}.db"


    with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            media_ids_sql = f"""SELECT hash FROM 'hashes'"""
            cur.execute(media_ids_sql)
            media_ids = cur.fetchall()

    # A list of single elements and not iterables:
    return list(chain.from_iterable(media_ids))

def paid_write_from_data(_id: tuple, model_id):
    profile = profiles.get_current_profile()

    database_path = path or pathlib.Path.home() / configPath / profile /"paid"/f"{model_id}.db"

    with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            model_insert_sql = f"""
            INSERT INTO 'hashes' (
                hash
            )
            VALUES (?);"""
            cur.execute(model_insert_sql, (_id,))
            conn.commit()
