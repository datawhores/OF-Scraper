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
import sqlite3

from rich.console import Console

import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.queries as queries
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


@wrapper.operation_wrapper
def create_products_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.productCreate)
        conn.commit()


@wrapper.operation_wrapper
def create_others_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.otherCreate)
        conn.commit()


@wrapper.operation_wrapper
def add_column_other_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.otherAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def add_column_products_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.productsAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def create_schema_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.schemaCreate)
        conn.commit()


@wrapper.operation_wrapper
def get_schema_changes(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(queries.schemaAll).fetchall()
        return set(list(map(lambda x: x[0], data)))


@wrapper.operation_wrapper
def add_flag_schema(flag, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            data = cur.execute(queries.schemaInsert, [flag, 1])
            conn.commit()
        except sqlite3.IntegrityError as e:
            log.debug("Error: Unique constraint on schema flags violation occurred", e)
            # You can choose to retry the insert with a modified flag value or take other actions
            pass


@wrapper.operation_wrapper
def get_all_others_transition(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(queries.othersALLTransition).fetchall()
        return data


@wrapper.operation_wrapper
def drop_others_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.othersDrop)
        conn.commit()


@wrapper.operation_wrapper
def write_others_table_transition(
    insertData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.othersInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def get_all_products_transition(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(queries.productsALLTransition).fetchall()
        return data


@wrapper.operation_wrapper
def drop_products_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.productsDrop)
        conn.commit()


@wrapper.operation_wrapper
def write_products_table_transition(
    insertData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.productsInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_models_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        if len(cur.execute(queries.modelDupeCheck, (model_id,)).fetchall()) == 0:
            cur.execute(queries.modelInsert, [model_id])
            conn.commit()


def modify_unique_constriant_others(model_id=None, username=None):
    data = get_all_others_transition(model_id=model_id, username=username)
    drop_others_table(model_id=model_id, username=username)
    create_others_table(model_id=model_id, username=username)
    write_others_table_transition(data, model_id=model_id, username=username)


def modify_unique_constriant_products(model_id=None, username=None):
    data = get_all_products_transition(model_id=model_id, username=username)
    drop_products_table(model_id=model_id, username=username)
    create_products_table(model_id=model_id, username=username)
    write_products_table_transition(data, model_id=model_id, username=username)
