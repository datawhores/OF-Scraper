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
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.utils.args.read as read_args
from ofscraper.utils.context.run_async import run

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
	created_at TIMESTAMP, 
    model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""
postInsert = f"""INSERT INTO 'posts'(
post_id, text,price,paid,archived,created_at,model_id)
VALUES (?, ?,?,?,?,?,?);"""
postUpdate = f"""UPDATE posts
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ?, model_id=?
WHERE post_id = ?;"""
timelinePostInfo = """
SELECT created_at,post_id FROM posts where archived=(0) and model_id=(?)
"""
postsALLTransition = """
SELECT post_id, text,price,paid,archived,created_at FROM posts;
"""
postsDrop = """
drop table posts;
"""
allPOSTCheck = """
SELECT post_id FROM posts
"""
postAddColumnID = """
ALTER TABLE posts ADD COLUMN model_id INTEGER;
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
                    data.date,
                    model_id,
                ),
                posts,
            )
        )
        cur.executemany(postInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_post_table_transition(
    inputData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as cur:
        ordered_keys = ('post_id', 'text', 'price', 'paid', 'archived', 'created_at')
        insertData = [tuple([data[key] for key in ordered_keys]+[model_id]) for data in inputData]
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
                ],
                posts,
            )
        )
        cur.executemany(postUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper
def get_timeline_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(timelinePostInfo, [model_id])
        data=[dict(row) for row in cur.fetchall()]
        return [dict(ele,created_at=arrow.get(ele.get("created_at")).float_timestamp) for ele in data]



@wrapper.operation_wrapper
def create_post_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postCreate)
        conn.commit()


@wrapper.operation_wrapper
def get_all_post_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allPOSTCheck)
        return [dict(row)["post_id"] for row in cur.fetchall()]


@wrapper.operation_wrapper
def get_all_posts_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postsALLTransition)
        return [dict(row) for row in cur.fetchall()]


@wrapper.operation_wrapper
def drop_posts_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postsDrop)
        conn.commit()


@wrapper.operation_wrapper
def add_column_post_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(postAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def get_archived_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(archivedPostInfo, [model_id])
        conn.commit()
        data=[dict(row) for row in cur.fetchall()]
        return [dict(ele,created_at=arrow.get(ele.get("created_at")).float_timestamp) for ele in data]


def modify_unique_constriant_posts(model_id=None, username=None):
    data = get_all_posts_transition(model_id=model_id, username=username)
    drop_posts_table(model_id=model_id, username=username)
    create_post_table(model_id=model_id, username=username)
    write_post_table_transition(data, model_id=model_id, username=username)


async def make_post_table_changes(all_posts, model_id=None, username=None):
    curr_id = set(get_all_post_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_posts))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_posts))
    if len(new_posts) > 0:
        new_posts = helpers.converthelper(new_posts)
        await write_post_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = helpers.converthelper(curr_posts)
        await update_posts_table(curr_posts, model_id=model_id, username=username)


def get_last_archived_date(model_id=None, username=None):
    data = get_archived_postinfo(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x.get("created_at"))[-1]


def get_last_timeline_date(model_id=None, username=None):
    data = get_timeline_postinfo(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x["created_at"])[-1]