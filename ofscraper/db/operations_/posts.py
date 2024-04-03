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

import arrow
from rich.console import Console

import ofscraper.db.operations_.helpers as helpers
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.utils.args.read as read_args
from ofscraper.db.operations_.profile import get_single_model

console = Console()
log = logging.getLogger("shared")

postCreate = """
CREATE TABLE IF NOT EXISTS posts (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
    pinned BOOLEAN,
	created_at TIMESTAMP, 
    model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""
postInsert = """INSERT INTO 'posts'(
post_id, text,price,paid,archived,pinned,created_at,model_id)
VALUES (?, ?,?,?,?,?,?,?);"""
postUpdate = """UPDATE posts
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ?, model_id=?
WHERE post_id = ? and model_id=(?);"""
timelinePostInfo = """
SELECT created_at,post_id FROM posts where archived=(0) and model_id=(?)
"""
postsALLTransition = """
SELECT post_id, text, price, paid, archived, created_at,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'model_id')
            THEN model_id
            ELSE NULL
       END AS model_id
FROM posts;
"""
postsDrop = """
drop table posts;
"""
allPOSTCheck = """
SELECT post_id FROM posts
"""

archivedPostInfo = """
SELECT created_at,post_id FROM posts where archived=(1) and model_id=(?)
"""


@wrapper.operation_wrapper_async
def write_post_table(posts: list, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = list(
            map(
                lambda data: (
                    data.id,
                    data.db_text,
                    data.price,
                    data.paid,
                    data.archived,
                    data.pinned,
                    data.date,
                    model_id,
                ),
                posts,
            )
        )
        cur.executemany(postInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def write_post_table_transition(
    inputData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as cur:
        ordered_keys = (
            "post_id",
            "text",
            "price",
            "paid",
            "archived",
            "pinned",
            "created_at",
            "model_id",
        )
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        cur.executemany(postInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def update_posts_table(posts: list, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        updateData = list(
            map(
                lambda data: [
                    data.db_text,
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                    model_id,
                    data.id,
                    model_id,
                ],
                posts,
            )
        )
        cur.executemany(postUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper_async
def get_timeline_postsinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(timelinePostInfo, [model_id])
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, created_at=arrow.get(ele.get("created_at")).float_timestamp)
            for ele in data
        ]


@wrapper.operation_wrapper_async
def create_post_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_post_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allPOSTCheck)
        return [dict(row)["post_id"] for row in cur.fetchall()]


@wrapper.operation_wrapper_async
def get_all_posts_transition(
    model_id=None, username=None, conn=None, database_model=None
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postsALLTransition)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                row,
                pinned=row.get("pinned"),
                model_id=row.get("model_id") or database_model,
            )
            for row in data
        ]


@wrapper.operation_wrapper_async
def drop_posts_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postsDrop)
        conn.commit()


@wrapper.operation_wrapper_async
def add_column_post_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)

            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE posts ADD COLUMN model_id INTEGER;")
            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def add_column_post_pinned(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'pinned') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)

            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE posts ADD COLUMN pinned BOOLEAN;")
            # Commit changes
            conn.commit()

        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def get_archived_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(archivedPostInfo, [model_id])
        conn.commit()
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, created_at=arrow.get(ele.get("created_at")).float_timestamp)
            for ele in data
        ]


async def modify_unique_constriant_posts(model_id=None, username=None):
    database_model = get_single_model(model_id=model_id, username=username)
    data = await get_all_posts_transition(
        model_id=model_id, username=username, database_model=database_model
    )
    await drop_posts_table(model_id=model_id, username=username)
    await create_post_table(model_id=model_id, username=username)
    await write_post_table_transition(data, model_id=model_id, username=username)


async def make_post_table_changes(all_posts, model_id=None, username=None):
    curr_id = set(await get_all_post_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_posts))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_posts))
    if len(new_posts) > 0:
        new_posts = helpers.converthelper(new_posts)
        await write_post_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = helpers.converthelper(curr_posts)
        await update_posts_table(curr_posts, model_id=model_id, username=username)


async def get_last_archived_date(model_id=None, username=None):
    data = await media.get_archived_media(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x["posted_at"] or 0)[-1].get("posted_at") or 0


async def get_last_timeline_date(model_id=None, username=None):
    data = await media.get_timeline_media(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x["posted_at"] or 0)[-1].get("posted_at") or 0
