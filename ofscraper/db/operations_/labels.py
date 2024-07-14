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

import ofscraper.classes.labels as labels_class
import ofscraper.db.utils.convert as convert
import ofscraper.db.operations_.posts as post_
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.utils.args.accessors.read as read_args
from ofscraper.db.operations_.profile import get_single_model_via_profile

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

labelSelectTransition = """
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
def create_labels_table(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelsCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def write_labels_table(
    label: dict, posts: dict, model_id=None, username=None, conn=None, **kwargs
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
    label: dict, posts: dict, model_id=None, username=None, conn=None, **kwargs
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
                    post.id,
                ),
                posts,
            )
        )
        curr.executemany(labelUpdate, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def write_labels_table_transition(
    inputData: list, model_id=None, username=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as curr:
        ordered_keys = ["label_id", "name", "type", "post_id", "model_id"]
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        curr.executemany(labelInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_labels_posts(label, model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as curr:
        curr.execute(labelPostsID, [model_id, label.label_id])
        return [dict(row)["post_id"] for row in curr.fetchall()]


@wrapper.operation_wrapper_async
def add_column_labels_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('labels') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)
            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE labels ADD COLUMN model_id INTEGER;")
            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Raise the error for handling


@wrapper.operation_wrapper_async
def drop_labels_table(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(labelDrop)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_labels_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        # Check for column existence (label_id)
        cur.execute("PRAGMA table_info('labels')")
        columns = [row[1] for row in cur.fetchall()]  # Get column names

        # Build SELECT clause dynamically
        select_clause = "label_id" if "label_id" in columns else "id"
        select_clause += ", model_id"  # Add model_id for clarity

        # Build the full query
        sql = f"""
        SELECT
            {select_clause},
            name, type, post_id
        FROM labels;
        """
        cur.execute(sql)
        # Execute the query
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                row,
                label_id=row.get("label_id") or row.get("id"),
                model_id=row.get("model_id") or database_model,
            )
            for row in data
        ]


async def rebuild_labels_table(model_id=None, username=None, db_path=None, **kwargs):
    database_model = get_single_model_via_profile(
        model_id=model_id, username=username, db_path=db_path
    )
    data = await get_all_labels_transition(
        model_id=model_id,
        username=username,
        database_model=database_model,
        db_path=db_path,
    )
    await drop_labels_table(model_id=model_id, username=username, db_path=db_path)
    await create_labels_table(model_id=model_id, username=username, db_path=db_path)
    await write_labels_table_transition(
        data, model_id=model_id, username=username, db_path=db_path
    )


async def make_label_table_changes(
    labels, model_id=None, username=None, posts=True, **kwargs
):
    labels = list(
        map(
            lambda x: (
                labels_class.Label(x, model_id, username)
                if not isinstance(x, labels_class.Label)
                else x
            ),
            labels,
        )
    )
    for label in labels:
        curr = set(
            await get_all_labels_posts(label, model_id=model_id, username=username)
        )
        new_posts = list(filter(lambda x: x.id not in curr, label.posts))
        curr_posts = list(filter(lambda x: x.id in curr, label.posts))
        if len(new_posts) > 0:
            new_posts = convert.converthelper(new_posts)
            await write_labels_table(
                label, new_posts, model_id=model_id, username=username
            )
        if read_args.retriveArgs().metadata and len(curr_posts) > 0:
            curr_posts = convert.converthelper(curr_posts)
            await update_labels_table(
                label, curr_posts, model_id=model_id, username=username
            )
    if posts:
        all_posts = [post for label in labels for post in label.posts]
        await post_.make_post_table_changes(
            all_posts, model_id=model_id, username=username
        )
