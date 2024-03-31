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
import ofscraper.db.queries as queries
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


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
                queries.profileDupeCheck, (model_id,)
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
        cur.execute(queries.profilesCreate)
        conn.commit()


@wrapper.operation_wrapper
def write_profile_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [model_id, username]
        if len(cur.execute(queries.profileDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(queries.profileInsert, insertData)
        else:
            insertData.append(model_id)
            cur.execute(queries.profileUpdate, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_profile_table_transition(insertData, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(queries.profileInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def check_profile_table_exists(model_id=None, username=None, conn=None):
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return False
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.profileTableCheck).fetchall()) > 0:
            conn.commit()
            return True
        conn.commit()
        return False


@wrapper.operation_wrapper
def checker_profile_unique(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profileInfo = cur.execute(queries.checkProfileTableUnique).fetchall()
            if not bool(profileInfo):
                return
            conn.commit()
            return profileInfo[0][2] == 1
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@wrapper.operation_wrapper
def get_all_profiles(model_id=None, username=None, conn=None) -> list:
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    if not pathlib.Path(database_path).exists():
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profiles = cur.execute(queries.profilesALL).fetchall()
            conn.commit()
            return profiles
        except sqlite3.OperationalError as E:
            None
        except Exception as E:
            raise E


@wrapper.operation_wrapper
def drop_profiles_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.profilesDrop)
        conn.commit()


@wrapper.operation_wrapper
def create_models_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.modelsCreate)
        conn.commit()


@wrapper.operation_wrapper
def write_models_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.modelDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(queries.modelInsert, [model_id])
            conn.commit()


def remove_unique_constriant_profile(model_id=None, username=None):
    data = get_all_profiles(model_id=model_id, username=username)
    drop_profiles_table(model_id=model_id, username=username)
    create_profile_table(model_id=model_id, username=username)
    write_profile_table_transition(data, model_id=model_id, username=username)
