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

import ofscraper.db.operations_.helpers as helpers
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.utils.args.read as read_args
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")

storiesCreate = """
CREATE TABLE IF NOT EXISTS stories (
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
storiesInsert = f"""INSERT INTO 'stories'(
post_id, text,price,paid,archived,created_at,model_id)
            VALUES (?, ?,?,?,?,?,?);"""
storiesUpdate = f"""UPDATE stories
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ? ,model_id=?
WHERE post_id = ?;"""

storiesAddColumnID = """
ALTER TABLE stories ADD COLUMN model_id INTEGER;
"""
storiesALLTransition = """
select post_id,text,price,paid,archived,created_at from stories
"""
storiesDrop = """
drop table stories;
"""


@wrapper.operation_wrapper
def create_stories_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(storiesCreate)
        conn.commit()


@wrapper.operation_wrapper
def write_stories_table(stories: dict, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        stories = helpers.converthelper(stories)
        insertData = list(
            map(
                lambda data: (
                    data.id,
                    data.db_text or data.title or "",
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                    model_id,
                ),
                stories,
            )
        )
        cur.executemany(storiesInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_stories_table_transition(
    insertData: dict, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(storiesInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def update_stories_table(stories: dict, model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        stories = helpers.converthelper(stories)
        updateData = list(
            map(
                lambda data: (
                    data.db_text or data.title or "",
                    data.price,
                    data.paid,
                    data.archived,
                    data.date,
                    model_id,
                    data.id,
                ),
                stories,
            )
        )
        cur.executemany(storiesUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper
def get_all_stories_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allStoriesCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper
def get_all_stories_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(storiesALLTransition)
        conn.commit()
        return cur.fetchall()


@wrapper.operation_wrapper
def add_column_stories_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(storiesAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def drop_stories_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(storiesDrop)
        conn.commit()


def modify_unique_constriant_stories(model_id=None, username=None):
    data = get_all_stories_transition(model_id=model_id, username=username)
    drop_stories_table(model_id=model_id, username=username)
    create_stories_table(model_id=model_id, username=username)
    write_stories_table_transition(data, model_id=model_id, username=username)


def make_stories_tables_changes(
    all_stories: dict, model_id=None, username=None, conn=None
):
    curr_id = set(get_all_stories_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_stories))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_stories))
    if len(new_posts) > 0:
        new_posts = helpers.converthelper(new_posts)
        write_stories_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = helpers.converthelper(curr_posts)
        update_stories_table(curr_posts, model_id=model_id, username=username)
