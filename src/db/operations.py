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
from itertools import chain
from hashlib import md5
from rich.console import Console
console=Console()
from ..constants import configPath, databaseFile
from ..utils import separate, profiles


def create_database(model_id, path=None):
    profile = profiles.get_current_profile()

    path = path or pathlib.Path.home() / configPath / profile / databaseFile

    with contextlib.closing(sqlite3.connect(path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            try:
                model_sql = f"""
                CREATE TABLE '{model_id}'(
                    id INTEGER PRIMARY KEY,
                    media_id INTEGER NOT NULL,
                    filename VARCHAR NOT NULL
                );"""
                cur.execute(model_sql)
            except sqlite3.OperationalError:
                pass


def write_from_data(data: tuple, model_id):
    profile = profiles.get_current_profile()

    database_path = pathlib.Path.home() / configPath / profile / databaseFile

    with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            model_insert_sql = f"""
            INSERT INTO '{model_id}'(
                media_id, filename
            )
            VALUES (?, ?);"""
            cur.execute(model_insert_sql, data)
            conn.commit()


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


def get_media_ids(model_id) -> list:
    profile = profiles.get_current_profile()

    database_path = pathlib.Path.home() / configPath / profile / databaseFile

    with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            media_ids_sql = f"""SELECT media_id FROM '{model_id}'"""
            cur.execute(media_ids_sql)
            media_ids = cur.fetchall()

    # A list of single elements and not iterables:
    return list(chain.from_iterable(media_ids))

def create_paid_database(model_id, path=None):
    profile = profiles.get_current_profile()
    path = path or pathlib.Path.home() / configPath / profile /"paid"/f"{model_id}.db"
    pathlib.Path(path).parent.mkdir(exist_ok=True,parents=True)
    with contextlib.closing(sqlite3.connect(path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            try:
                model_sql = f"""
                CREATE TABLE IF NOT EXISTS hashes (id integer PRIMARY KEY, hash int);"""
                cur.execute(model_sql)
            except sqlite3.OperationalError:
                pass

def get_paid_media_ids(model_id,path=None) -> list:
    profile = profiles.get_current_profile()

    database_path = path or pathlib.Path.home() / configPath / profile /"paid"/f"{model_id}.db"


    with contextlib.closing(sqlite3.connect(database_path,check_same_thread=False)) as conn:
        with contextlib.closing(conn.cursor()) as cur:
            media_ids_sql = f"""SELECT hash FROM 'hashes'"""
            cur.execute(media_ids_sql)
            media_ids = cur.fetchall()

    # A list of single elements and not iterables:
    return list(chain.from_iterable(media_ids))

def paid_write_from_data(_id: tuple, model_id,path=None):
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
