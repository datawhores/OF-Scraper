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
import ofscraper.db.queries as queries
import ofscraper.utils.args.read as read_args
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


@wrapper.operation_wrapper
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
        cur.executemany(queries.postInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_post_table_transition(
    insertData: list, model_id=None, username=None, conn=None
):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(queries.postInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
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
        cur.executemany(queries.postUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper
def get_timeline_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.timelinePostInfo, [model_id])
        conn.commit()
        return list(
            map(lambda x: (arrow.get(x[0]).float_timestamp, x[1]), cur.fetchall())
        )


@wrapper.operation_wrapper
def create_post_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postCreate)
        conn.commit()


@wrapper.operation_wrapper
def get_all_post_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.allPOSTCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper
def get_all_posts_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postsALLTransition)
        conn.commit()
        return cur.fetchall()


@wrapper.operation_wrapper
def drop_posts_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.postsDrop)
        conn.commit()


@wrapper.operation_wrapper
def add_column_post_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(queries.profileAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


@wrapper.operation_wrapper
def get_archived_postinfo(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(queries.archivedPostInfo, [model_id])
        conn.commit()
        return list(
            map(lambda x: (arrow.get(x[0]).float_timestamp, x[1]), cur.fetchall())
        )


def modify_unique_constriant_posts(model_id=None, username=None):
    data = get_all_posts_transition(model_id=model_id, username=username)
    drop_posts_table(model_id=model_id, username=username)
    create_post_table(model_id=model_id, username=username)
    write_post_table_transition(data, model_id=model_id, username=username)


def make_post_table_changes(all_posts, model_id=None, username=None):
    curr_id = get_all_post_ids(model_id=model_id, username=username)
    new_posts = list(filter(lambda x: x.id not in curr_id, all_posts))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_posts))
    if len(new_posts) > 0:
        new_posts = helpers.converthelper(new_posts)
        write_post_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = helpers.converthelper(curr_posts)
        update_posts_table(curr_posts, model_id=model_id, username=username)


def get_last_archived_date(model_id=None, username=None):
    data = get_archived_postinfo(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x[0])[-1][0]


def get_last_timeline_date(model_id=None, username=None):
    data = get_timeline_postinfo(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x)[-1]
