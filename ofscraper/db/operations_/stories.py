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

import ofscraper.db.utils.convert as convert
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.utils.args.accessors.read as read_args
from ofscraper.db.operations_.profile import get_single_model_via_profile

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
storiesInsert = """INSERT INTO 'stories'(
post_id, text,price,paid,archived,created_at,model_id)
            VALUES (?, ?,?,?,?,?,?);"""
storiesUpdate = """UPDATE stories
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ? ,model_id=?
WHERE post_id = ? and model_id=(?);"""


storiesSelectTransition = """
SELECT post_id,text,price,paid,archived,created_at,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('stories') WHERE name = 'model_id')
            THEN model_id
            ELSE NULL
       END AS model_id
FROM stories;

"""
storiesDrop = """
drop table stories;
"""
allStoriesCheck = """
SELECT post_id FROM stories
"""


@wrapper.operation_wrapper_async
def create_stories_table(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(storiesCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def write_stories_table(
    stories: dict, model_id=None, username=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        stories = convert.converthelper(stories)
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


@wrapper.operation_wrapper_async
def write_stories_table_transition(
    inputData: dict, model_id=None, username=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        ordered_keys = [
            "post_id",
            "text",
            "price",
            "paid",
            "archived",
            "created_at",
            "model_id",
        ]
        insertData = [tuple([data[key] for key in ordered_keys]) for data in inputData]
        cur.executemany(storiesInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def update_stories_table(
    stories: dict, model_id=None, username=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        stories = convert.converthelper(stories)
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
                    model_id,
                ),
                stories,
            )
        )
        cur.executemany(storiesUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_stories_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allStoriesCheck)
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper_async
def get_all_stories_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(storiesSelectTransition)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(row, model_id=row.get("model_id") or database_model) for row in data
        ]


@wrapper.operation_wrapper_async
def add_column_stories_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Separate statements with conditional execution
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('stories') WHERE name = 'model_id') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]
            if alter_required == 0:
                cur.execute("ALTER TABLE stories ADD COLUMN model_id INTEGER;")

            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def drop_stories_table(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(storiesDrop)
        conn.commit()


async def rebuild_stories_table(model_id=None, username=None, db_path=None, **kwargs):
    database_model = get_single_model_via_profile(
        model_id=model_id, username=username, db_path=db_path
    )
    data = await get_all_stories_transition(
        model_id=model_id,
        username=username,
        database_model=database_model,
        db_path=db_path,
    )

    await drop_stories_table(model_id=model_id, username=username, db_path=db_path)
    await create_stories_table(model_id=model_id, username=username, db_path=db_path)
    await write_stories_table_transition(
        data, model_id=model_id, username=username, db_path=db_path
    )


async def make_stories_table_changes(
    all_stories: dict, model_id=None, username=None, conn=None, **kwargs
):
    all_stories_filtered = filter(
        lambda x: x.responsetype in {"stories", "highlights"}, all_stories
    )

    curr_id = set(await get_all_stories_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_stories_filtered))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_stories_filtered))
    if len(new_posts) > 0:
        new_posts = convert.converthelper(new_posts)
        await write_stories_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = convert.converthelper(curr_posts)
        await update_stories_table(curr_posts, model_id=model_id, username=username)
