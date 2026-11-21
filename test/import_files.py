"""user_data.db files of several ages, for the tests of the import into
PostgreSQL (test_postgres_import.py runs without a server,
test_postgres_import_live.py with one).
"""

import asyncio
import contextlib
import sqlite3

import ofscraper.db.operations as operations
import ofscraper.db.operations_.others as others
from ofscraper.db.transition import modify_tables

# the tables as released in 2.6.4.1 (2023): no model_id, labels, models or
# schema_flags, and one username per file
TABLES_2023 = """
CREATE TABLE medias (
    id INTEGER NOT NULL, media_id INTEGER, post_id INTEGER NOT NULL,
    link VARCHAR, directory VARCHAR, filename VARCHAR, size INTEGER,
    api_type VARCHAR, media_type VARCHAR, preview INTEGER, linked VARCHAR,
    downloaded INTEGER, created_at TIMESTAMP,
    PRIMARY KEY (id), UNIQUE (media_id));
CREATE TABLE messages (
    id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,
    price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP,
    user_id INTEGER, PRIMARY KEY (id), UNIQUE (post_id));
CREATE TABLE posts (
    id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,
    price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP,
    PRIMARY KEY (id), UNIQUE (post_id));
CREATE TABLE others (
    id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,
    price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP,
    PRIMARY KEY (id), UNIQUE (post_id));
CREATE TABLE products (
    id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,
    price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP,
    title VARCHAR, PRIMARY KEY (id), UNIQUE (post_id));
CREATE TABLE profiles (
    id INTEGER NOT NULL, user_id INTEGER NOT NULL, username VARCHAR NOT NULL,
    PRIMARY KEY (id), UNIQUE (username));
CREATE TABLE stories (
    id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,
    price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP,
    PRIMARY KEY (id), UNIQUE (post_id));
"""
# the columns added last, and the upgrade steps that add them
NEWEST = {
    "media_skip_permanent": ("medias", "skip_permanent"),
    "messages_group_id": ("messages", "group_id"),
    "posts_mentions": ("posts", "mentions"),
    "posts_purchase_type": ("posts", "purchase_type"),
}


def sql(path, statement, rows=None):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        if rows is None:
            found = conn.execute(statement).fetchall()
        else:
            found = conn.executemany(statement, rows).fetchall()
        conn.commit()
        return found


def current_file(path, creator, name="a_creator", site=None):
    """A database as this version makes it, with a few rows for `creator`."""
    path.parent.mkdir(parents=True, exist_ok=True)

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)
        if site:
            await others.write_site_flag(site, db_path=path)

    asyncio.run(make())
    sql(path, "INSERT INTO profiles (user_id, username) VALUES (?, ?)", [(creator, name)])
    sql(path, "INSERT INTO models (model_id) VALUES (?)", [(creator,)])
    sql(
        path,
        "INSERT INTO posts (post_id, text, price, paid, archived, pinned, stream,"
        " opened, created_at, model_id, is_deleted) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (20, "second 100% 'quoted'", 0, 0, 0, 1, 0, 1, "2024-03-02T10:00:00+00:00", creator, 0),
            (10, "first\nline two\ttab \\ slash", 9.99, 1, 1, 0, 0, 0, "2024-03-01 09:30:00", creator, 1),
        ],
    )
    sql(
        path,
        "INSERT INTO medias (media_id, post_id, link, directory, filename, size,"
        " api_type, media_type, preview, linked, downloaded, created_at, posted_at,"
        " duration, unlocked, hash, model_id, skip_permanent)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 10, "https://example.invalid/1", "folder", "one.jpg", 2**40, "Timeline",
             "Images", 0, None, 1, "2024-03-01T09:30:00+00:00", 1709285400, None, 1,
             "abc", creator, None),
            (2, 10, None, None, None, None, "Timeline", "Videos", 1, None, 0, "", None,
             "00:01:02", 0, None, creator, 1),
            (1, 20, None, "folder", "one.jpg", 5, "Pinned", "Images", 0, None, 1,
             "2024-03-02T10:00:00+00:00", None, None, 1, None, creator, None),
        ],
    )
    sql(
        path,
        "INSERT INTO messages (post_id, text, price, paid, archived, created_at,"
        " user_id, model_id, is_deleted) VALUES (?,?,?,?,?,?,?,?,?)",
        [(30, "a message", 5, 1, 0, "2024-03-03T00:00:00+00:00", 7, creator, 0)],
    )
    sql(
        path,
        "INSERT INTO stories (post_id, text, price, paid, archived, created_at,"
        " model_id) VALUES (?,?,?,?,?,?,?)",
        [(40, None, 0, 0, 0, "2024-03-04T00:00:00+00:00", creator)],
    )
    sql(
        path,
        "INSERT INTO labels (label_id, name, type, post_id, model_id) VALUES (?,?,?,?,?)",
        [(900, "favourites", "posts", 10, creator)],
    )
    return path


def file_before_newest_columns(path, creator):
    """current_file, as it was before the columns added last."""
    current_file(path, creator)
    for flag, (table, column) in NEWEST.items():
        sql(path, f"ALTER TABLE {table} DROP COLUMN {column}")
        sql(path, f"DELETE FROM schema_flags WHERE flag_name = '{flag}'")
    return path


def without_the_dates(path):
    """A database as it was before the dates of a creator's names were kept
    (#643): no first_seen_at or last_seen_at, and the upgrade step not done."""
    for column in ("first_seen_at", "last_seen_at"):
        sql(path, f"ALTER TABLE profiles DROP COLUMN {column}")
    sql(path, "DELETE FROM schema_flags WHERE flag_name = 'profiles_seen_at'")
    return path


def file_2023(path, creator, name="a_creator"):
    """A database last used by the 2023 release."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.executescript(TABLES_2023)
        conn.execute("INSERT INTO profiles (user_id, username) VALUES (?, ?)", (creator, name))
        conn.executemany(
            "INSERT INTO posts (post_id, text, price, paid, archived, created_at)"
            " VALUES (?,?,?,?,?,?)",
            [
                (10, "an old post", 0, 0, 0, "2023-01-05T10:00:00+00:00"),
                (11, "a paid one", 15, 1, 1, "2023-01-06T10:00:00+00:00"),
            ],
        )
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, link, directory, filename, size,"
            " api_type, media_type, preview, linked, downloaded, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (1, 10, "https://example.invalid/1", "folder", "old.jpg", 100, "Timeline",
                 "images", 0, None, 1, "2023-01-05T10:00:00+00:00"),
                (2, 11, None, None, None, None, "Timeline", "videos", 0, None, 0,
                 "2023-01-06T10:00:00+00:00"),
            ],
        )
        conn.execute(
            "INSERT INTO messages (post_id, text, price, paid, archived, created_at,"
            " user_id) VALUES (30, 'hello', 0, 0, 0, '2023-01-07T10:00:00+00:00', 7)"
        )
        conn.commit()
    return path
