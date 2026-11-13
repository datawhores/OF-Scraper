"""A brand-new database gets no backup of itself (#312).

New tables are created in an older layout and then upgraded. The upgrade backs
the database up first, which is right for a database an older version left
behind, but a database created moments ago has nothing older to keep. The
same goes for the periodic backup taken when a model is scraped.

Each test builds a real SQLite database in a temporary folder.
"""

import asyncio
import shutil

import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.transition as transition
import ofscraper.utils.cache.cache as cache
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.others import get_schema_changes

MODEL_ID = 31200
USERNAME = "newdbmodel"


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


@pytest.fixture
def scrape_db(model_db, monkeypatch):
    # the periodic backup is separate from the transition backup under test
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    return model_db


def backups(db):
    folder = db.parent / "backup"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def old_schema_backups(db):
    return [name for name in backups(db) if name.startswith("old_schema_")]


def call(func, *args, **kwargs):
    # inside a running loop the app's @run functions return a coroutine; calling
    # them outside one leaves an event loop open
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


def merge_into(tmp_path, target):
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    return asyncio.run(merge.MergeDatabase()(source, target))


def older_layout(db):
    """A database as an older version left it: tables, but no schema flags."""
    call(operations.create_tables, db_path=db)
    assert get_group_difference(db_path=db)


def test_merge_into_a_new_folder_writes_no_backup(tmp_path):
    target = tmp_path / "target"
    target.mkdir()

    merge_into(tmp_path, target)

    db = target / "user_data.db"
    assert db.exists()
    assert not (target / "backup").exists()
    assert not get_group_difference(db_path=db)


def test_first_scrape_writes_no_old_schema_backup(scrape_db):
    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    assert scrape_db.exists()
    assert old_schema_backups(scrape_db) == []
    assert not get_group_difference(db_path=scrape_db)


def test_merge_into_an_older_database_backs_it_up_first(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    db = target / "user_data.db"
    older_layout(db)

    merge_into(tmp_path, target)

    assert backups(db) == ["old_schema_db_backup.db"]
    assert get_group_difference(db_path=(target / "backup" / "old_schema_db_backup.db"))
    assert not get_group_difference(db_path=db)


def test_scrape_of_an_older_database_backs_it_up_first(scrape_db):
    older_layout(scrape_db)

    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    assert len(old_schema_backups(scrape_db)) == 1
    assert old_schema_backups(scrape_db)[0].startswith(f"old_schema_{MODEL_ID}_")
    assert not get_group_difference(db_path=scrape_db)


def test_current_database_is_left_alone(scrape_db):
    call(operations.create_tables, db_path=scrape_db)
    call(transition.modify_tables, db_path=scrape_db)
    shutil.rmtree(scrape_db.parent / "backup", ignore_errors=True)
    before = get_schema_changes(db_path=scrape_db)

    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    assert backups(scrape_db) == []
    assert get_schema_changes(db_path=scrape_db) == before


@pytest.fixture
def failing_upgrade(monkeypatch):
    async def fail(**kwargs):
        raise RuntimeError("upgrade failed")

    monkeypatch.setattr(transition, "modify_tables_constraints_and_columns", fail)


def test_failed_upgrade_of_a_new_database_keeps_the_original_error(
    tmp_path, failing_upgrade
):
    db = tmp_path / "user_data.db"
    call(operations.create_tables, db_path=db)

    with pytest.raises(RuntimeError, match="upgrade failed"):
        call(transition.modify_tables, db_path=db, new_db=True)

    assert not (tmp_path / "backup").exists()


def test_failed_upgrade_of_an_older_database_restores_the_backup(
    tmp_path, failing_upgrade
):
    db = tmp_path / "user_data.db"
    older_layout(db)

    with pytest.raises(RuntimeError, match="upgrade failed"):
        call(transition.modify_tables, db_path=db)

    assert backups(db) == ["old_schema_db_backup.db"]
    # the column upgrades that ran before the failure were rolled back
    assert not get_schema_changes(db_path=db)


def test_first_scrape_writes_no_periodic_backup(model_db):
    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    assert model_db.exists()
    assert backups(model_db) == []


def test_existing_database_still_gets_the_periodic_backup(model_db):
    call(operations.create_tables, db_path=model_db)
    call(transition.modify_tables, db_path=model_db)
    shutil.rmtree(model_db.parent / "backup", ignore_errors=True)
    (model_db.parent / "backup").mkdir()

    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    assert backups(model_db) == ["user_data_copy_1.db"]
