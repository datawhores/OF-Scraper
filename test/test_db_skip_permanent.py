"""medias.skip_permanent marks a permanent skip by skip_download_script (#351).

Such an item is saved as downloaded with no file. The marker tells it apart
from a real download and from other items saved with no file, so a later
feature can undo it. Older databases gain the column empty (NULL) through the
usual upgrade step, and table rebuilds and Merge Databases keep it.

Each test builds a real SQLite database in a temporary folder with the app's
own create, upgrade, rebuild and merge code. The downloads that set the
marker are tested in test_size_limit_skip.py and test_drm_size_limits.py.
"""

import asyncio
import contextlib
import sqlite3

import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.transition as transition
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.profile import write_models_table, write_profile_table

MODEL_ID = 35100
USERNAME = "skipmodel"
FLAG = "media_skip_permanent"


def call(func, *args, **kwargs):
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


def rows(db, sql, *args):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return conn.execute(sql, args).fetchall()


def columns(db, table):
    return [r[1] for r in rows(db, f"PRAGMA table_info({table})")]


def new_db(db):
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)


def insert_media(db, media_id, downloaded, skip_permanent=None, with_marker=True):
    cols = "media_id, post_id, link, api_type, media_type, downloaded, model_id"
    values = [media_id, 9000 + media_id, None, "Timeline", "Images", downloaded, MODEL_ID]
    if with_marker:
        cols += ", skip_permanent"
        values.append(skip_permanent)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(
            f"INSERT INTO medias ({cols}) VALUES ({', '.join('?' * len(values))})",
            values,
        )
        conn.commit()


def markers(db):
    return rows(
        db, "SELECT media_id, downloaded, skip_permanent FROM medias ORDER BY media_id"
    )


def test_new_database_has_the_column(tmp_path):
    db = tmp_path / "user_data.db"
    new_db(db)
    assert "skip_permanent" in columns(db, "medias")
    assert not get_group_difference(db_path=db)


def test_old_database_gets_the_column_empty(tmp_path):
    # a database as the previous version left it: every earlier flag, no column
    db = tmp_path / "user_data.db"
    new_db(db)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute("ALTER TABLE medias DROP COLUMN skip_permanent")
        conn.execute("DELETE FROM schema_flags WHERE flag_name = ?", (FLAG,))
        conn.commit()
    insert_media(db, 1, 1, with_marker=False)
    insert_media(db, 2, 0, with_marker=False)
    assert get_group_difference(db_path=db) == {FLAG}

    call(transition.modify_tables, db_path=db)

    assert not get_group_difference(db_path=db)
    # old rows keep their values, with no marker
    assert markers(db) == [(1, 1, None), (2, 0, None)]


def test_table_rebuild_keeps_the_marker(tmp_path):
    db = tmp_path / "user_data.db"
    new_db(db)
    insert_media(db, 1, 1, skip_permanent=1)
    insert_media(db, 2, 1)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "DELETE FROM schema_flags WHERE flag_name = ?",
            [("media_post_id_constraint_added",), ("media_bool_changes",)],
        )
        conn.commit()

    call(transition.modify_tables, db_path=db)

    assert not get_group_difference(db_path=db)
    assert markers(db) == [(1, 1, 1), (2, 1, None)]


def test_merge_keeps_the_marker(tmp_path):
    source = tmp_path / "old" / "a" / "user_data.db"
    source.parent.mkdir(parents=True)
    new_db(source)
    insert_media(source, 1, 1, skip_permanent=1)
    insert_media(source, 2, 1)
    target = tmp_path / "new"
    target.mkdir()

    failures, _, _ = asyncio.run(merge.MergeDatabase()(tmp_path / "old", target))

    assert failures == []
    assert markers(target / "user_data.db") == [(1, 1, 1), (2, 1, None)]
