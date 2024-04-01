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

from rich.console import Console

import ofscraper.db.operations_.helpers as helpers
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.utils.args.read as read_args
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
labelInsert = """INSERT INTO 'labels'(
label_id,name, type, post_id,model_id)
VALUES ( ?,?,?,?,?);"""


labelUpdate = """Update 'labels'
SET label_id=?,name=?,type=?,post_id=?,model_id=?
WHERE label_id=(?) and model_id=(?) and post_id=(?);"""
labelPostsID = """
SELECT post_id  FROM  labels where model_id=(?) and label_id=(?)
"""
labelAddColumnID = """
BEGIN TRANSACTION;
  SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('labels') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;
  IF alter_required = 0 THEN  -- Check for false (model_id doesn't exist)
    ALTER TABLE labels ADD COLUMN model_id INTEGER;
  END IF;
COMMIT TRANSACTION;
"""
labelALLTransition = """
SELECT
    CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('labels') WHERE name = 'label_id')
        THEN label_id
        ELSE id
    END AS label_id,
        CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('labels') WHERE name = 'model_id')
        THEN model_id
        ELSE Null
    END AS model_id,
    name, type, post_id
FROM labels;
"""
labelDrop = """
drop table labels;
"""


@wrapper.operation_wrapper_async
def create_labels_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelsCreate)
        conn.commit()


@wrapper.operation_wrapper_async
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


@wrapper.operation_wrapper_async
def update_labels_table(
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
                    label.label_id,
                    model_id,
                    post.id
                ),
                posts,
            )
        )
        curr.executemany(labelUpdate, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def write_labels_table_transition(
    inputData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as curr:
        ordered_keys=["label_id","name", "type", "post_id","model_id"]
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        curr.executemany(labelInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_labels_posts(label,model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as curr:
        curr.execute(labelPostsID, [model_id,label.label_id])
        return [dict(row)["post_id"] for row in curr.fetchall()]


@wrapper.operation_wrapper_async
def add_column_labels_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelAddColumnID)
        conn.commit() 


@wrapper.operation_wrapper_async
def drop_labels_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelDrop)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_labels_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelALLTransition)
        return [dict(row) for row in cur.fetchall()]

async def modify_unique_constriant_labels(model_id=None, username=None):
    data = await get_all_labels_transition(model_id=model_id, username=username)
    await drop_labels_table(model_id=model_id, username=username)
    await create_labels_table(model_id=model_id, username=username)
    await write_labels_table_transition(data, model_id=model_id, username=username)

async def make_label_table_changes(label, model_id=None, username=None):
    curr = set( await get_all_labels_posts( label,model_id=model_id,username=username))
    new_posts = list(filter(lambda x: x.id not in curr, label.posts))
    curr_posts = list(filter(lambda x: x.id in curr, label.posts))
    if len(new_posts) > 0:
        new_posts = helpers.converthelper(new_posts)
        await write_labels_table(label,new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = helpers.converthelper(curr_posts)
        await update_labels_table(label,curr_posts, model_id=model_id, username=username)