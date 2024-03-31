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
import pathlib
import sqlite3

from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations_.wrapper as wrapper
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")
profilesCreate = """
CREATE TABLE IF NOT EXISTS profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	username VARCHAR NOT NULL,
	PRIMARY KEY (id)
)
"""
modelsCreate = """
CREATE TABLE IF NOT EXISTS models (
	id INTEGER NOT NULL,
	model_id INTEGER NOT NULL,
	UNIQUE (model_id)
	PRIMARY KEY (id)
)
"""
profileDupeCheck = """
SELECT * FROM profiles where user_id=(?)
"""
profileTableCheck = """
SELECT name FROM sqlite_master WHERE type='table' AND name='profiles';
"""
profileInsert = f"""INSERT INTO 'profiles'(
user_id,username)
VALUES (?, ?);"""
profileUpdate = f"""Update 'profiles'
SET
user_id=?,username=?
WHERE user_id=(?);"""
modelDupeCheck = """
SELECT * FROM models where model_id=(?)
"""
modelInsert = f"""
INSERT INTO models (model_id)
VALUES (?);
"""
profilesALL = """
select user_id,username from profiles
"""
profilesDrop = """
DROP TABLE profiles;
"""


@wrapper.operation_wrapper
def get_profile_info(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            modelinfo = cur.execute(
                profileDupeCheck, (model_id,)
            ).fetchall() or [(None,)]
            conn.commit()
            return modelinfo[0][-1]
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@wrapper.operation_wrapper
def create_profile_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(profilesCreate)
        conn.commit()


@wrapper.operation_wrapper
def write_profile_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [model_id, username]
        if len(cur.execute(profileDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(profileInsert, insertData)
        else:
            insertData.append(model_id)
            cur.execute(profileUpdate, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_profile_table_transition(insertData, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(profileInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def check_profile_table_exists(model_id=None, username=None, conn=None):
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return False
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(profileTableCheck).fetchall()) > 0:
            conn.commit()
            return True
        conn.commit()
        return False



@wrapper.operation_wrapper
def get_all_profiles(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profiles = cur.execute(profilesALL).fetchall()
            conn.commit()
            return profiles
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@wrapper.operation_wrapper
def drop_profiles_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(profilesDrop)
        conn.commit()


@wrapper.operation_wrapper
def create_models_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(modelsCreate)
        conn.commit()


@wrapper.operation_wrapper
def write_models_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(modelDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(modelInsert, [model_id])
            conn.commit()


def remove_unique_constriant_profile(model_id=None, username=None):
    data = get_all_profiles(model_id=model_id, username=username)
    drop_profiles_table(model_id=model_id, username=username)
    create_profile_table(model_id=model_id, username=username)
    write_profile_table_transition(data, model_id=model_id, username=username)
