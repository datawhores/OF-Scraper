"""stash_sync reading user_data.db files that no scraper made (#631).

A file that was put together by another program, or rebuilt by hand, may
have tables without an id column, an id that isn't the order the rows were
saved in, or a view where a table was. Reading PostgreSQL as well must not
change what such a file gives: these pass on the version before it too.
"""

import os
import sqlite3
from contextlib import closing

from test_stash_sync import FakeStash

from ofscraper.commands.stash_sync import read_model, sync

DAY = "2025-03-01T10:00:00+00:00"
MEDIA = "media_id, post_id, directory, filename, api_type, media_type, downloaded, posted_at, created_at"


def build(db, *statements):
    db.parent.mkdir(parents=True)
    with closing(sqlite3.connect(db)) as conn, conn:
        for statement in statements:
            conn.execute(statement)
    return db


def test_tables_without_an_id_column_are_read(tmp_path):
    db = build(
        tmp_path / "a_folder" / "user_data.db",
        f"CREATE TABLE medias ({MEDIA})",
        "CREATE TABLE posts (post_id, text)",
        "CREATE TABLE messages (post_id, text)",
        "INSERT INTO posts VALUES (10, 'a post')",
        "INSERT INTO messages VALUES (11, 'a message')",
        f"INSERT INTO medias VALUES (1, 10, 'folder', 'one.jpg', 'Timeline', 'Images', 1, '{DAY}', NULL)",
        f"INSERT INTO medias VALUES (2, 11, 'folder', 'two.jpg', 'Messages', 'Images', 1, '{DAY}', NULL)",
    )

    username, files = read_model(db)

    assert username is None
    assert [(f["path"], f["meta"]["details"], f["meta"]["date"]) for f in files] == [
        (os.path.join("folder", "one.jpg"), "a post", "2025-03-01"),
        (os.path.join("folder", "two.jpg"), "a message", "2025-03-01"),
    ]
    stash = FakeStash(images=[f["path"] for f in files])
    report = sync([db], stash, apply=True)
    assert report["totals"] == {"files": 2, "updated": 2}
    assert report["models"][0]["performer"] == "a_folder"


def test_rows_are_read_in_the_order_the_file_gives_them(tmp_path):
    """Not by an id column, which here runs against the order the rows were
    saved in. Only the username is the one with the highest id."""
    db = build(
        tmp_path / "1" / "user_data.db",
        f"CREATE TABLE medias (id INT PRIMARY KEY, {MEDIA})",
        "CREATE TABLE posts (id INT PRIMARY KEY, post_id, text)",
        "CREATE TABLE profiles (id INT PRIMARY KEY, user_id, username)",
        "INSERT INTO profiles VALUES (9, 1, 'highest_id')",
        "INSERT INTO profiles VALUES (3, 1, 'saved_last')",
        # a post saved twice: the text saved last is the one kept
        "INSERT INTO posts VALUES (9, 10, 'saved first')",
        "INSERT INTO posts VALUES (3, 10, 'saved last')",
        # a file saved twice: the row saved first names its type
        f"INSERT INTO medias VALUES (9, 1, 10, 'folder', 'both.jpg', 'Timeline', 'Images', 1, '{DAY}', NULL)",
        f"INSERT INTO medias VALUES (3, 2, 10, 'folder', 'both.jpg', 'Timeline', 'Videos', 1, '{DAY}', NULL)",
        f"INSERT INTO medias VALUES (2, 3, 10, 'folder', 'after.jpg', 'Timeline', 'Images', 1, '{DAY}', NULL)",
    )

    username, files = read_model(db)

    assert username == "highest_id"
    assert [(os.path.basename(f["path"]), f["media_type"]) for f in files] == [
        ("both.jpg", "Images"),
        ("after.jpg", "Images"),
    ]
    assert files[0]["meta"]["details"] == "saved last"
    assert files[0]["media_ids"] == {"10": "1"}


def test_a_view_is_not_a_table_except_for_media(tmp_path):
    """Posts, messages and names are looked for among the tables only. The
    media is asked for by name, table or not."""
    db = build(
        tmp_path / "1" / "user_data.db",
        f"CREATE TABLE kept_medias (id INTEGER PRIMARY KEY, {MEDIA})",
        "CREATE VIEW medias AS SELECT * FROM kept_medias",
        "CREATE TABLE kept_posts (id INTEGER PRIMARY KEY, post_id, text, purchase_type)",
        "CREATE VIEW posts AS SELECT * FROM kept_posts",
        # asked for a post id, this one would stop the run: it isn't asked
        "CREATE VIEW messages AS SELECT text, purchase_type AS group_id FROM kept_posts",
        "CREATE VIEW stories AS SELECT purchase_type FROM kept_posts",
        "CREATE TABLE kept_profiles (id INTEGER PRIMARY KEY, user_id, username)",
        "CREATE VIEW profiles AS SELECT * FROM kept_profiles",
        "INSERT INTO kept_profiles VALUES (1, 1, 'behind_a_view')",
        "INSERT INTO kept_posts VALUES (1, 10, 'text behind a view', 'post')",
        f"INSERT INTO kept_medias VALUES (1, 1, 10, 'folder', 'one.jpg', 'Timeline', 'Images', 1, '{DAY}',"
        " '2024-01-01T10:00:00+00:00')",
    )

    username, (entry,) = read_model(db)

    assert username is None
    # no text, and the day it was posted: the view's columns are seen
    assert entry["meta"] == {"code": "10", "date": "2025-03-01", "details": None, "title": None}
    assert entry["path"] == os.path.join("folder", "one.jpg")
