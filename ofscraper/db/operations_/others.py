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
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")

otherCreate = """
CREATE TABLE IF NOT EXISTS others (
	id INTEGER NOT NULL,  
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
	model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""
productCreate = """
CREATE TABLE IF NOT EXISTS products (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP,
    title VARCHAR, 
    model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""
schemaCreate = """
CREATE TABLE if not exists schema_flags (flag_name TEXT PRIMARY KEY, flag_value TEXT);
"""
otherAddColumnID = """
ALTER Table others ADD COLUMN model_id INTEGER;
"""
productsAddColumnID = """
ALTER Table products ADD COLUMN model_id INTEGER;
"""
schemaAll = """
SELECT flag_name FROM schema_flags WHERE flag_value = 1;
"""
schemaInsert = """
INSERT INTO 'schema_flags'( flag_name,flag_value)
VALUES (?,?)
"""
othersALLTransition = """
SELECT text,price,paid,archived,created_at FROM others;
"""
othersDrop = """
drop table others;
"""
othersInsert = f"""INSERT INTO 'others'(
post_id, text,price,paid,archived,
created_at,model_id)
VALUES (?, ?,?,?,?,?,?);"""
productsALLTransition = """
SELECT text,price,paid,archived,created_at FROM products;
"""
productsDrop = """
drop table products;
"""
productsInsert = f"""INSERT INTO 'products'(
post_id, text,price,paid,archived,
created_at,title,model_id)
VALUES (?, ?,?,?,?,?,?,?);"""


@wrapper.operation_wrapper
def create_products_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(productCreate)
        conn.commit()


@wrapper.operation_wrapper
def create_others_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(otherCreate)
        conn.commit()


@wrapper.operation_wrapper
def add_column_other_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(otherAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def add_column_products_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(productsAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def create_schema_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(schemaCreate)
        conn.commit()


@wrapper.operation_wrapper
def get_schema_changes(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(schemaAll).fetchall()
        return set(list(map(lambda x: x[0], data)))


@wrapper.operation_wrapper
def add_flag_schema(flag, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            data = cur.execute(schemaInsert, [flag, 1])
            conn.commit()
        except sqlite3.IntegrityError as e:
            log.debug("Error: Unique constraint on schema flags violation occurred", e)
            pass



@wrapper.operation_wrapper
def get_all_others_transition(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(othersALLTransition).fetchall()
        return data


@wrapper.operation_wrapper
def drop_others_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(othersDrop)
        conn.commit()


@wrapper.operation_wrapper
def write_others_table_transition(
    insertData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(othersInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def get_all_products_transition(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(productsALLTransition).fetchall()
        return data


@wrapper.operation_wrapper
def drop_products_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(productsDrop)
        conn.commit()


@wrapper.operation_wrapper
def write_products_table_transition(
    insertData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(productsInsert, insertData)
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
