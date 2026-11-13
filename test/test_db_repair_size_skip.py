"""Old databases: un-mark the files the size-skip bug saved as downloaded (#352).

Before #326, a file skipped by a size limit was saved as downloaded with no
file, and its row got the media type "Forced_skippeds" (#319). The download
columns are written for every post of the media, so its rows in other posts
were left downloaded with no file too. A later scrape writes the real media
type back, so after that only an automatic backup still shows the label.

A one-time step of the database upgrade un-marks the rows it can identify for
certain, after backing the database up. Each test builds a real SQLite
database in a temporary folder with the app's own schema code, in the layout
the previous version left (every flag but the repair's), and runs the real
per-creator start-up (`table_init_create`).
"""

import asyncio
import contextlib
import shutil
import sqlite3

import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.transition as transition
import ofscraper.utils.cache.cache as cache
from ofscraper.db.backup import create_backup
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.media import get_media_ids_downloaded_model_sync
from ofscraper.db.operations_.profile import write_models_table, write_profile_table

MODEL_ID = 35200
OTHER_MODEL = 35201
USERNAME = "a-creator"
FLAG = "media_size_skip_repaired"
NO_FILE = (None, None, None, None)
A_FILE = ("/media/a-creator/Videos", "file.mp4", 1000, "abc123")


@pytest.fixture
def model_db(monkeypatch, tmp_path):
    db = tmp_path / "data" / "user_data.db"
    db.parent.mkdir()
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    # keep the periodic backup's timestamps and counters out of the real cache
    store = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value, **k: store.update({key: value}))
    return db


def call(func, *args, **kwargs):
    # inside a running loop the app's @run functions return a coroutine; calling
    # them outside one leaves an event loop open
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


def layout_before_the_repair(db):
    """A database as the previous version left it: every flag but the repair's."""
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)
    sql(db, "DELETE FROM schema_flags WHERE flag_name = ?", FLAG)
    # (empty before this fix, which had no such flag)
    assert get_group_difference(db_path=db) <= {FLAG}


def sql(db, statement, *params):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(statement, params)
        conn.commit()


def add(db, media_id, post_id, media_type, downloaded, file=NO_FILE, model_id=MODEL_ID):
    """A media row as the app writes it: the scrape's insert, then a download update."""
    directory, filename, size, hash_ = file
    sql(
        db,
        "INSERT INTO medias (media_id, post_id, link, api_type, media_type, preview,"
        " linked, created_at, posted_at, model_id, duration, unlocked, directory,"
        " filename, size, downloaded, hash) VALUES (?, ?, 'https://cdn.example/x',"
        " 'Timeline', ?, 0, NULL, '2026-01-02T03:04:05', '2026-01-02T03:04:05', ?,"
        " NULL, 1, ?, ?, ?, ?, ?)",
        media_id, post_id, media_type, model_id, directory, filename, size,
        downloaded, hash_,
    )


def set_type(db, media_id, media_type):
    # what the next scrape does: it writes the real type back
    sql(db, "UPDATE medias SET media_type = ? WHERE media_id = ?", media_type, media_id)


def medias(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return conn.execute(
            "SELECT media_id, post_id, model_id, media_type, downloaded, directory,"
            " filename, size, hash FROM medias ORDER BY model_id, media_id, post_id"
        ).fetchall()


def downloaded(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return {
            (media_id, post_id, model_id): value
            for media_id, post_id, model_id, value in conn.execute(
                "SELECT media_id, post_id, model_id, downloaded FROM medias"
            )
        }


def backups(db):
    folder = db.parent / "backup"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def start_run():
    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)


@pytest.fixture
def old_db(model_db):
    """A database the bug went through, with a periodic and an old_schema backup
    taken while some of its rows still had the label."""
    db = model_db
    layout_before_the_repair(db)
    # labelled in the database now, and its copy in another post
    add(db, 1, 10, "Forced_skippeds", 1)
    add(db, 1, 11, "Videos", 1)
    # labelled only in the periodic backup, in two posts
    add(db, 2, 20, "Forced_skippeds", 1)
    add(db, 2, 21, "Videos", 1)
    # labelled in the periodic backup, downloaded with a file since
    add(db, 3, 30, "Forced_skippeds", 1)
    # labelled only in the old_schema backup (set below)
    add(db, 8, 80, "Videos", 1)
    # labelled, but the same media was downloaded with a file through another post
    add(db, 6, 60, "Forced_skippeds", 1, A_FILE)
    add(db, 6, 61, "Videos", 1, A_FILE)
    sql(db, "UPDATE medias SET directory = NULL, filename = NULL, size = NULL,"
            " hash = NULL WHERE media_id = 6 AND post_id = 60")
    # downloaded with no file, not identified (e.g. a skip_download_script skip)
    add(db, 4, 40, "Images", 1)
    # downloaded with a file
    add(db, 5, 50, "Images", 1, A_FILE)
    # the same media id under another creator, downloaded with no file
    add(db, 1, 10, "Videos", 1, model_id=OTHER_MODEL)
    # not downloaded yet
    add(db, 9, 90, "Images", None)

    assert create_backup(MODEL_ID, USERNAME).name == "user_data_copy_1.db"
    old_schema = create_backup(MODEL_ID, USERNAME, backup="old_schema_db_backup.db")
    # an older upgrade's copy, from when media 8 still had the label
    sql(old_schema, "UPDATE medias SET media_type = 'Forced_skippeds' WHERE media_id = 8")
    # since the backups: a scrape wrote the real types back, and media 3 was
    # downloaded (e.g. with --force-all)
    for media_id in (2, 3):
        set_type(db, media_id, "Videos")
    sql(db, "UPDATE medias SET directory = ?, filename = ?, size = ?, hash = ?"
            " WHERE media_id = 3", *A_FILE)
    return db


UNMARKED = {(1, 10, MODEL_ID), (1, 11, MODEL_ID), (2, 20, MODEL_ID), (2, 21, MODEL_ID),
            (8, 80, MODEL_ID)}


def test_identified_rows_are_set_back_to_not_downloaded(old_db):
    before = downloaded(old_db)

    start_run()

    after = downloaded(old_db)
    assert {key for key, value in after.items() if before[key] != value} == UNMARKED
    assert all(after[key] is None for key in UNMARKED)
    # the next run downloads them: they're not in the downloaded list any more
    still = get_media_ids_downloaded_model_sync(model_id=MODEL_ID, db_path=old_db)
    assert still == {3, 4, 5, 6}
    assert not get_group_difference(db_path=old_db)


def test_other_rows_are_unchanged(old_db):
    before = {row[:3]: row for row in medias(old_db)}

    start_run()

    for row in medias(old_db):
        key = row[:3]
        if key in UNMARKED:
            # only downloaded changes; the label stays until the next scrape
            assert row[:4] + row[5:] == before[key][:4] + before[key][5:]
        else:
            assert row == before[key]


def test_backup_is_made_first(old_db):
    old = set(backups(old_db))

    start_run()

    (new,) = [name for name in backups(old_db) if name not in old
              and name.startswith(f"old_schema_{MODEL_ID}_")]
    copy = old_db.parent / "backup" / new
    # the backup holds the rows as they were, and the layout before the repair
    assert {key: value for key, value in downloaded(copy).items() if key in UNMARKED} == {
        key: 1 for key in UNMARKED
    }
    assert get_group_difference(db_path=copy) == {FLAG}


def test_backups_are_only_read(old_db):
    folder = old_db.parent / "backup"
    before = {p.name: p.read_bytes() for p in folder.iterdir()}

    call(transition.repair_tables, db_path=old_db)

    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_an_unreadable_backup_is_skipped(old_db):
    (old_db.parent / "backup" / "user_data_copy_2.db").write_bytes(b"not a database")

    start_run()

    assert all(downloaded(old_db)[key] is None for key in UNMARKED)


def test_second_run_changes_nothing(old_db):
    start_run()
    assert downloaded(old_db)[(1, 10, MODEL_ID)] is None
    rows, files = medias(old_db), backups(old_db)
    # downloaded with no file again, as a skip_download_script skip leaves it
    sql(old_db, "UPDATE medias SET downloaded = 1 WHERE media_id = 1")

    start_run()

    assert backups(old_db) == files
    assert downloaded(old_db)[(1, 10, MODEL_ID)] == 1
    assert [r for r in medias(old_db) if r[0] != 1] == [r for r in rows if r[0] != 1]


def labelled_only_in_a_backup(db, name):
    """Media 2 downloaded with no file; only backup/`name` still has its label."""
    layout_before_the_repair(db)
    add(db, 2, 20, "Forced_skippeds", 1)
    add(db, 2, 21, "Videos", 1)
    (db.parent / "backup").mkdir(exist_ok=True)
    shutil.copy(db, db.parent / "backup" / name)
    set_type(db, 2, "Videos")


def test_backup_replaced_by_the_periodic_copy_is_read_first(model_db):
    labelled_only_in_a_backup(model_db, "user_data_copy_2.db")
    # the periodic copy is due, and goes to user_data_copy_2.db
    cache.set(f"{USERNAME}_{MODEL_ID}_db_backup", 0)
    cache.set(f"{USERNAME}_{MODEL_ID}_dbcounter", 1)

    start_run()

    copy = model_db.parent / "backup" / "user_data_copy_2.db"
    assert downloaded(copy)[(2, 20, MODEL_ID)] == 1
    assert "Forced_skippeds" not in {row[3] for row in medias(copy)}
    assert downloaded(model_db)[(2, 20, MODEL_ID)] is None
    assert downloaded(model_db)[(2, 21, MODEL_ID)] is None


def test_merge_target_backup_replaced_by_the_upgrade_is_read_first(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    db = target / "user_data.db"
    # a merge target's upgrade backup has a fixed name, so it's replaced each time
    labelled_only_in_a_backup(db, "old_schema_db_backup.db")
    source = tmp_path / "source"
    source.mkdir()

    asyncio.run(merge.MergeDatabase()(source, target))

    copy = target / "backup" / "old_schema_db_backup.db"
    assert "Forced_skippeds" not in {row[3] for row in medias(copy)}
    assert downloaded(db)[(2, 20, MODEL_ID)] is None
    assert downloaded(db)[(2, 21, MODEL_ID)] is None


def test_database_without_such_rows_is_unchanged(model_db):
    layout_before_the_repair(model_db)
    add(model_db, 4, 40, "Images", 1)
    add(model_db, 5, 50, "Images", 1, A_FILE)
    add(model_db, 9, 90, "Videos", None)
    before = medias(model_db)

    start_run()

    assert medias(model_db) == before
    assert not get_group_difference(db_path=model_db)


def test_permanent_script_skip_is_left_downloaded(model_db):
    # a skip_download_script `skip-permanent` row is downloaded with no file
    # on purpose (#351): the repair treats it as having a file, so neither it
    # nor the media's other rows are un-marked, even with the old label
    layout_before_the_repair(model_db)
    add(model_db, 6, 60, "Forced_skippeds", 1)
    add(model_db, 6, 61, "Videos", 1)
    sql(model_db, "UPDATE medias SET skip_permanent = 1 WHERE media_id = 6")
    # a labelled row without the marker is still repaired
    add(model_db, 7, 70, "Forced_skippeds", 1)

    start_run()

    assert downloaded(model_db)[(6, 60, MODEL_ID)] == 1
    assert downloaded(model_db)[(6, 61, MODEL_ID)] == 1
    assert downloaded(model_db)[(7, 70, MODEL_ID)] is None
    assert not get_group_difference(db_path=model_db)


def test_repair_works_on_a_table_without_the_marker_column(model_db):
    # the column is added before the repair runs; the repair doesn't need it
    from ofscraper.db.operations_.media import repair_size_skipped_media

    layout_before_the_repair(model_db)
    sql(model_db, "ALTER TABLE medias DROP COLUMN skip_permanent")
    add(model_db, 7, 70, "Forced_skippeds", 1)

    assert call(repair_size_skipped_media, db_path=model_db) == 1
    assert downloaded(model_db)[(7, 70, MODEL_ID)] is None


def test_new_database_gets_the_flag_without_a_backup(model_db):
    start_run()

    assert not get_group_difference(db_path=model_db)
    assert backups(model_db) == []
