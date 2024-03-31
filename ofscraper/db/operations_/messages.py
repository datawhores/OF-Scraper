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

messagesCreate = """
CREATE TABLE IF NOT EXISTS messages (
id INTEGER NOT NULL,
post_id INTEGER NOT NULL,
text VARCHAR,
price INTEGER,
paid INTEGER,
archived BOOLEAN,
created_at TIMESTAMP,
user_id INTEGER,
model_id INTEGER,
PRIMARY KEY (id),
UNIQUE (post_id,model_id)
)
"""
messagesInsert = f"""INSERT INTO 'messages'(
post_id, text,price,paid,archived,
created_at,user_id,model_id)
            VALUES (?, ?,?,?,?,?,?,?);"""
messagesUpdate = f"""UPDATE messages
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ?, user_id=?,model_id=?
WHERE post_id = ?;"""
allMessagesCheck = """
SELECT post_id FROM messages
"""
messagesALLTransition = """
select post_id,text,price,paid,archived,created_at,user_id from messages
"""
messagesDrop = """
drop table messages;
"""
messagesData = """
SELECT created_at,post_id FROM messages where model_id=(?)
"""
messagesAddColumnID = """
ALTER TABLE messages ADD COLUMN model_id INTEGER;
"""


@wrapper.operation_wrapper
def create_message_table(model_id=None, username=None, conn=None):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(messagesCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def update_messages_table(messages: dict, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        updateData = list(
            map(
                lambda message: (
                    message.db_text,
                    message.price,
                    message.paid,
                    message.archived,
                    message.date,
                    message.fromuser,
                    model_id,
                    message.id,
                ),
                messages,
            )
        )
        cur.executemany(messagesUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper_async
def write_messages_table(messages: dict, model_id=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = list(
            map(
                lambda message: (
                    message.id,
                    message.db_text,
                    message.price,
                    message.paid,
                    message.archived,
                    message.date,
                    message.fromuser,
                    model_id,
                ),
                messages,
            )
        )
        cur.executemany(messagesInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def write_messages_table_transition(
    insertData: list, model_id=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        insertData = [[*ele, model_id] for ele in insertData]
        cur.executemany(messagesInsert, insertData)
        conn.commit()


@wrapper.operation_wrapper
def get_all_messages_ids(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allMessagesCheck)
        conn.commit()
        return list(map(lambda x: x[0], cur.fetchall()))


@wrapper.operation_wrapper
def get_all_messages_transition(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(messagesALLTransition)
        conn.commit()
        return cur.fetchall()


@wrapper.operation_wrapper
def drop_messages_table(model_id=None, username=None, conn=None) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(messagesDrop)
        conn.commit()


@wrapper.operation_wrapper
def get_messages_post_info(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(messagesData, [model_id])
        conn.commit()
        return list(
            map(
                lambda x: {"date": arrow.get(x[0]).float_timestamp, "id": x[1]},
                cur.fetchall(),
            )
        )


@wrapper.operation_wrapper
def add_column_messages_ID(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(messagesAddColumnID)
            conn.commit()
        except sqlite3.OperationalError as E:
            if not str(E) == "duplicate column name: model_id":
                raise E


def modify_unique_constriant_messages(model_id=None, username=None):
    data = get_all_messages_transition(model_id=model_id, username=username)
    drop_messages_table(model_id=model_id, username=username)
    create_message_table(model_id=model_id, username=username)
    write_messages_table_transition(data, model_id=model_id, username=username)


async def make_messages_table_changes(all_messages, model_id=None, username=None):
    curr_id = set(get_all_messages_ids(model_id=model_id, username=username))
    new_posts = list(filter(lambda x: x.id not in curr_id, all_messages))
    curr_posts = list(filter(lambda x: x.id in curr_id, all_messages))
    if len(new_posts) > 0:
        new_posts = helpers.converthelper(new_posts)
        await write_messages_table(new_posts, model_id=model_id, username=username)
    if read_args.retriveArgs().metadata and len(curr_posts) > 0:
        curr_posts = helpers.converthelper(curr_posts)
        await update_messages_table(curr_posts, model_id=model_id, username=username)


def get_last_message_date(model_id=None, username=None):
    data = get_messages_post_info(model_id=model_id, username=username)
    return sorted(data, key=lambda x: x.get("date"))[-1].get("date")
