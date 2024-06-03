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
from ofscraper.db.operations_.profile import get_single_model_via_profile

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

schemaAll = """
SELECT flag_name FROM schema_flags WHERE flag_value = 1;
"""
schemaInsert = """
INSERT OR REPLACE INTO schema_flags (flag_name, flag_value)
VALUES (?, ?);
"""
othersSelectTransition = """
SELECT text,price,paid,archived,created_at ,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('others') WHERE name = 'model_id')
            THEN model_id
            ELSE NULL
       END AS model_id
FROM others;
"""
othersDrop = """
drop table others;
"""
othersInsert = """INSERT INTO 'others'(
post_id, text,price,paid,archived,
created_at,model_id)
VALUES (?, ?,?,?,?,?,?);"""
productsSelectTransition = """
SELECT text,price,paid,archived,created_at ,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('products') WHERE name = 'model_id')
            THEN model_id
            ELSE NULL
       END AS model_id
FROM products;
"""
productsDrop = """
drop table products;
"""
productsInsert = """INSERT INTO 'products'(
post_id, text,price,paid,archived,
created_at,title,model_id)
VALUES (?, ?,?,?,?,?,?,?);"""


@wrapper.operation_wrapper_async
def create_products_table(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(productCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def create_others_table(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(otherCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def add_column_other_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:

        try:
            # Separate statements with conditional execution
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('others') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]
            if alter_required == 0:
                cur.execute("ALTER TABLE others ADD COLUMN model_id INTEGER;")

            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def add_column_products_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:

        try:
            # Separate statements with conditional execution
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('products') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]
            if alter_required == 0:
                cur.execute("ALTER TABLE products ADD COLUMN model_id INTEGER;")

            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def create_schema_table(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(schemaCreate)
        conn.commit()


@wrapper.operation_wrapper
def get_schema_changes(model_id=None, username=None, conn=None, db_path=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        data = cur.execute(schemaAll).fetchall()
        return set(list(map(lambda x: x[0], data)))


@wrapper.operation_wrapper_async
def add_flag_schema(flag, model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(schemaInsert, [flag, 1])
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_others_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(othersSelectTransition)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(row, model_id=row.get("model_id") or database_model) for row in data
        ]


@wrapper.operation_wrapper_async
def drop_others_table(model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(othersDrop)
        conn.commit()


@wrapper.operation_wrapper_async
def write_others_table_transition(
    inputData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        ordered_keys = ["text", "price", "paid", "archived", "created_at", "model_id"]
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        cur.executemany(othersInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_products_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(productsSelectTransition)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(row, model_id=row.get("model_id") or database_model) for row in data
        ]


@wrapper.operation_wrapper_async
def drop_products_table(model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(productsDrop)
        conn.commit()


@wrapper.operation_wrapper_async
def write_products_table_transition(
    inputData, model_id=None, conn=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        ordered_keys = ["text", "price", "paid", "archived", "created_at", "model_id"]
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        cur.executemany(productsInsert, insertData)
        conn.commit()


async def rebuild_others_table(model_id=None, username=None, db_path=None, **kwargs):
    database_model = get_single_model_via_profile(
        model_id=model_id, username=username, db_path=db_path
    )
    data = await get_all_others_transition(
        model_id=model_id,
        username=username,
        database_model=database_model,
        db_path=db_path,
    )
    await drop_others_table(model_id=model_id, username=username, db_path=db_path)
    await create_others_table(model_id=model_id, username=username, db_path=db_path)
    await write_others_table_transition(
        data, model_id=model_id, username=username, db_path=db_path
    )


async def rebuild_products_table(model_id=None, username=None, db_path=None, **kwargs):
    database_model = get_single_model_via_profile(
        model_id=model_id, username=username, db_path=db_path
    )
    data = await get_all_products_transition(
        model_id=model_id,
        username=username,
        database_model=database_model,
        db_path=db_path,
    )
    await drop_products_table(model_id=model_id, username=username, db_path=db_path)
    await create_products_table(model_id=model_id, username=username, db_path=db_path)
    await write_products_table_transition(
        data, model_id=model_id, username=username, db_path=db_path
    )
