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

import ofscraper.classes.of.posts as posts_
import ofscraper.db.utils.convert as convert
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.utils.rebuild as rebuild
from ofscraper.db.operations_.profile import get_single_model_via_profile
import ofscraper.utils.settings as settings

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
    stream BOOLEAN,
    opened BOOLEAN,
	created_at TIMESTAMP, 
    model_id INTEGER, 
    is_deleted BOOLEAN DEFAULT 0, -- NEW COLUMN
    purchase_type VARCHAR,
    mentions VARCHAR,
	PRIMARY KEY (id),
	UNIQUE (post_id,model_id)
)
"""
postInsert = """INSERT INTO 'posts'(
post_id, text,price,paid,archived,pinned,stream,opened,created_at,model_id,purchase_type,mentions)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?);"""

postInsertTransition = """INSERT INTO 'posts'(
post_id, text,price,paid,archived,pinned,stream,opened,created_at,model_id,is_deleted,purchase_type,mentions)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);"""

# mentions is only replaced by a list: an item without one keeps what's stored.
# purchase_type isn't updated here: postFillMissing sets it once, and a
# timeline scan of a bought post must not clear it
postUpdate = """UPDATE posts
SET text = ?, price = ?, paid = ?, archived = ?, pinned=?,stream=?,opened=?,created_at = ?, model_id=?, is_deleted=0,
mentions = COALESCE(?, mentions)
WHERE post_id = ? and model_id=(?);"""

# fills the newer columns of rows saved before they existed, on every scan
postFillMissing = """UPDATE posts
SET purchase_type = COALESCE(purchase_type, ?), mentions = COALESCE(mentions, ?)
WHERE post_id = ? AND model_id = (?) AND (purchase_type IS NULL OR mentions IS NULL);"""

postIgnoreGhost = """
UPDATE posts
SET is_deleted = 1
WHERE post_id = (?) AND model_id = (?);
"""

timelinePostInfo = """
SELECT created_at,post_id FROM posts 
WHERE archived=(0) AND model_id=(?) AND (is_deleted = 0 OR is_deleted IS NULL)
"""
archivedPostInfo = """
SELECT created_at,post_id FROM posts 
WHERE archived=(1) AND model_id=(?) AND (is_deleted = 0 OR is_deleted IS NULL)
"""
streamsPostInfo = """
SELECT created_at,post_id FROM posts 
WHERE stream=(1) AND model_id=(?) AND (is_deleted = 0 OR is_deleted IS NULL)
"""

postsSelectTransition = """
SELECT post_id, text, price, paid, archived, created_at,
    CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'model_id')
            THEN model_id
            ELSE NULL
       END AS model_id,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'pinned')
            THEN pinned
            ELSE NULL
       END AS pinned,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'stream')
            THEN stream
            ELSE NULL
       END AS stream,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'opened')
            THEN opened
            ELSE NULL
       END AS opened,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'is_deleted')
            THEN is_deleted
            ELSE 0
       END AS is_deleted,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'purchase_type')
            THEN purchase_type
            ELSE NULL
       END AS purchase_type,
       CASE WHEN EXISTS (SELECT 1 FROM pragma_table_info('posts') WHERE name = 'mentions')
            THEN mentions
            ELSE NULL
       END AS mentions
       FROM posts;
"""

allPOSTCheck = """
SELECT post_id FROM posts
"""

deletedPostsCheck = """
SELECT post_id FROM posts WHERE is_deleted = 1 AND model_id = (?)
"""


@wrapper.operation_wrapper_async
def write_post_table(posts: list, model_id=None, username=None, conn=None, **kwargs):
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
                    data.stream,
                    data.opened,
                    data.date,
                    model_id,
                    data.purchase_type,
                    data.db_mentions,
                ),
                posts,
            )
        )
        cur.executemany(postInsert, insertData)
        conn.commit()


def posts_transition_rows(inputData: list) -> list:
    ordered_keys = (
        "post_id",
        "text",
        "price",
        "paid",
        "archived",
        "pinned",
        "stream",
        "opened",
        "created_at",
        "model_id",
        "is_deleted",
    )
    # optional columns: a row read before they existed has no value
    optional_keys = ("purchase_type", "mentions")
    return [
        tuple([data[key] for key in ordered_keys] + [data.get(key) for key in optional_keys])
        for data in inputData
    ]


@wrapper.operation_wrapper_async
def write_post_table_transition(
    inputData: list, model_id=None, username=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(postInsertTransition, posts_transition_rows(inputData))
        conn.commit()


@wrapper.operation_wrapper_async
def replace_posts_table(inputData: list, model_id=None, conn=None, **kwargs):
    rebuild.replace_table(
        conn, "posts", postCreate, postInsertTransition, posts_transition_rows(inputData)
    )


@wrapper.operation_wrapper_async
def update_posts_table(posts: list, model_id=None, username=None, conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        updateData = list(
            map(
                lambda data: [
                    data.db_text,
                    data.price,
                    data.paid,
                    data.archived,
                    data.pinned,
                    data.stream,
                    data.opened,
                    data.date,
                    model_id,
                    data.db_mentions,
                    data.id,
                    model_id,
                ],
                posts,
            )
        )
        cur.executemany(postUpdate, updateData)
        conn.commit()


@wrapper.operation_wrapper_async
def fill_posts_missing_fields(
    posts: list, model_id=None, username=None, conn=None, **kwargs
):
    fillData = [
        [data.purchase_type, data.db_mentions, data.id, model_id]
        for data in posts
        if data.purchase_type is not None or data.db_mentions is not None
    ]
    if not fillData:
        return
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(postFillMissing, fillData)
        conn.commit()


@wrapper.operation_wrapper_async
def get_timeline_posts_info(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(timelinePostInfo, [model_id])
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, created_at=arrow.get(ele.get("created_at") or 0).float_timestamp)
            for ele in data
        ]


@wrapper.operation_wrapper_async
def create_post_table(model_id=None, username=None, conn=None, db_path=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def get_all_post_ids(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(allPOSTCheck)
        return [dict(row)["post_id"] for row in cur.fetchall()]


@wrapper.operation_wrapper_async
def get_all_posts_transition(
    model_id=None, username=None, conn=None, database_model=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(postsSelectTransition)
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(
                row,
                pinned=row.get("pinned"),
                model_id=row.get("model_id") or database_model,
                is_deleted=row.get("is_deleted"),
            )
            for row in data
        ]


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
def add_column_post_stream(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'stream') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)

            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE posts ADD COLUMN stream BOOLEAN;")
            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def add_column_post_opened(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            # Check if column exists (separate statement)
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'opened') THEN 1 ELSE 0 END AS alter_required;"
            )
            alter_required = cur.fetchone()[0]  # Fetch the result (0 or 1)

            # Add column if necessary (conditional execution)
            if alter_required == 0:
                cur.execute("ALTER TABLE posts ADD COLUMN opened BOOLEAN;")
            # Commit changes
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e  # Rollback in case of errors


@wrapper.operation_wrapper_async
def mark_post_as_deleted(post_ids, username=None, conn=None, model_id=None, **kwargs):
    if not post_ids:
        return
    with contextlib.closing(conn.cursor()) as curr:
        insertData = [[post_id, model_id] for post_id in post_ids]
        curr.executemany(postIgnoreGhost, insertData)
        conn.commit()


@wrapper.operation_wrapper_async
def add_column_post_is_deleted(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'is_deleted') THEN 1 ELSE 0 END AS alter_required;"
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "ALTER TABLE posts ADD COLUMN is_deleted BOOLEAN DEFAULT 0;"
                )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def add_column_post_purchase_type(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'purchase_type') THEN 1 ELSE 0 END AS alter_required;"
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE posts ADD COLUMN purchase_type VARCHAR;")
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def add_column_post_mentions(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(
                "SELECT CASE WHEN EXISTS (SELECT 1 FROM PRAGMA_TABLE_INFO('posts') WHERE name = 'mentions') THEN 1 ELSE 0 END AS alter_required;"
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE posts ADD COLUMN mentions VARCHAR;")
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def get_archived_post_info(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(archivedPostInfo, [model_id])
        conn.commit()
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, created_at=arrow.get(ele.get("created_at") or 0).float_timestamp)
            for ele in data
        ]


@wrapper.operation_wrapper_async
def get_streams_post_info(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(streamsPostInfo, [model_id])
        conn.commit()
        data = [dict(row) for row in cur.fetchall()]
        return [
            dict(ele, created_at=arrow.get(ele.get("created_at") or 0).float_timestamp)
            for ele in data
        ]


async def rebuild_posts_table(model_id=None, username=None, db_path=None, **kwargs):
    database_model = get_single_model_via_profile(
        model_id=model_id, username=username, db_path=db_path
    )
    data = await get_all_posts_transition(
        model_id=model_id,
        username=username,
        database_model=database_model,
        db_path=db_path,
    )
    await replace_posts_table(
        data, model_id=model_id, username=username, db_path=db_path
    )


async def make_post_table_changes(all_posts, model_id=None, username=None, **kwargs):
    all_posts_data = list(
        map(
            lambda x: posts_.Post(x, model_id, username) if isinstance(x, dict) else x,
            all_posts,
        )
    )

    curr_id = set(await get_all_post_ids(model_id=model_id, username=username))
    unique_post_data = list({ele.id: ele for ele in all_posts_data}.values())

    new_posts = list(filter(lambda x: x.id not in curr_id, unique_post_data))
    curr_posts = list(filter(lambda x: x.id in curr_id, unique_post_data))
    if len(new_posts) > 0:
        new_posts = convert.converthelper(new_posts)
        await write_post_table(new_posts, model_id=model_id, username=username)
    if settings.get_settings().metadata and len(curr_posts) > 0:
        curr_posts = convert.converthelper(curr_posts)
        await update_posts_table(curr_posts, model_id=model_id, username=username)
    if len(curr_posts) > 0:
        await fill_posts_missing_fields(curr_posts, model_id=model_id, username=username)


async def get_oldest_archived_date(model_id=None, username=None, **kwargs):
    data = await media.get_archived_media(model_id=model_id, username=username)
    last_item = sorted(data, key=lambda x: arrow.get(x["posted_at"]))[0]
    return last_item["posted_at"] or 0


async def get_youngest_archived_date(model_id=None, username=None, **kwargs):
    data = await media.get_archived_media(model_id=model_id, username=username)
    last_item = sorted(data, key=lambda x: arrow.get(x["posted_at"]))[-1]
    return last_item["posted_at"] or 0


async def get_oldest_streams_date(model_id=None, username=None, **kwargs):
    data = await media.get_streams_media(model_id=model_id, username=username)
    last_item = sorted(data, key=lambda x: arrow.get(x["posted_at"]))[0]
    return last_item["posted_at"] or 0


async def get_youngest_streams_date(model_id=None, username=None, **kwargs):
    data = await media.get_streams_media(model_id=model_id, username=username)
    last_item = sorted(data, key=lambda x: arrow.get(x["posted_at"]))[-1]
    return last_item["posted_at"] or 0


async def get_oldest_timeline_date(model_id=None, username=None, **kwargs):
    data = await media.get_timeline_media(model_id=model_id, username=username)
    last_item = sorted(data, key=lambda x: arrow.get(x["posted_at"]))[0]
    return last_item["posted_at"]


async def get_youngest_timeline_date(model_id=None, username=None, **kwargs):
    data = await media.get_timeline_media(model_id=model_id, username=username)
    last_item = sorted(data, key=lambda x: arrow.get(x["posted_at"]))[-1]
    return last_item["posted_at"]


@wrapper.operation_wrapper_async
def get_deleted_post_ids(model_id=None, username=None, conn=None, **kwargs) -> set:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(deletedPostsCheck, [model_id])
        return set([dict(row)["post_id"] for row in cur.fetchall()])
