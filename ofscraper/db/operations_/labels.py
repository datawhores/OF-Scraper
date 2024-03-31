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
labelsCreate = """
CREATE TABLE IF NOT EXISTS labels (
	id INTEGER NOT NULL, 
    label_id INTEGER,
	name VARCHAR, 
	type VARCHAR, 
	post_id INTEGER, 
    model_id INTEGER,
	PRIMARY KEY (id)
    UNIQUE (post_id,label_id,model_id)
)
"""
labelInsert = f"""INSERT INTO 'labels'(
label_id,name, type, post_id,model_id)
VALUES ( ?,?,?,?,?);"""
labelID = """
SELECT id,post_id  FROM  labels where model_id=(?)
"""
labelAddColumnID = """
ALTER TABLE labels ADD COLUMN user_id VARCHAR;
"""
labelALLTransition = """
SELECT label_id,name,type,post_id FROM labels;
"""
labelALLTransition2 = """
SELECT id,name,type,post_id FROM labels;
"""
labelDrop = """
drop table labels;
"""


@wrapper.operation_wrapper
def create_labels_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelsCreate)
        conn.commit()


@wrapper.operation_wrapper
def write_labels_table(
    label: dict, posts: dict, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as curr:
        insertData = list(
            map(
                lambda post: (
                    label.label_id,
                    label.name,
                    label.type,
                    post.id,
                    model_id,
                ),
                posts,
            )
        )
        curr.executemany(labelInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_labels_table_transition(
    insertData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as curr:
        insertData = [[*ele, model_id] for ele in insertData]
        curr.executemany(labelInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def get_all_labels_ids(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as curr:
        curr.execute(labelID, [model_id])
        conn.commit()
        return curr.fetchall()


@wrapper.operation_wrapper
def add_column_labels_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(labelAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def drop_labels_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelDrop)
        conn.commit()


@wrapper.operation_wrapper
def get_all_labels_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(labelALLTransition)
            return cur.fetchall()
        except sqlite3.OperationalError:
            cur.execute(labelALLTransition2)
            return cur.fetchall()


def modify_unique_constriant_labels(model_id=None, username=None):
    data = get_all_labels_transition(model_id=model_id, username=username)
    drop_labels_table(model_id=model_id, username=username)
    create_labels_table(model_id=model_id, username=username)
    write_labels_table_transition(data, model_id=model_id, username=username)
