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
import pathlib
import sqlite3

import arrow
from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.db.difference import get_group_difference
from ofscraper.utils.paths.manage import copy_path

console = Console()
log = logging.getLogger("shared")


def restore_backup_transition(backup, model_id, username, db_path=None, **kwargs):
    database = db_path or placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    copy_path(backup, database)
    log.debug(f"restored {database} from {backup}")


def create_backup_transition(model_id=None, username=None, db_path=None, **kwargs):

    if (
        len(get_group_difference(model_id=model_id, username=username, db_path=db_path))
        > 0
    ):
        log.info("creating a backup before transition")
        backup_name = (
            f"old_schema_{model_id}_{arrow.now().float_timestamp}_db_backup.db"
            if model_id
            else "old_schema_db_backup.db"
        )
        new_backup_path = create_backup(
            model_id, username, backup=backup_name, db_path=db_path
        )
        log.info(f"transition backup created at {new_backup_path}")
        check_backup(model_id, username, new_backup_path, db_path=db_path)
        return new_backup_path


def check_backup(model_id, username, new_path, db_path=None, **kwargs):
    if not new_path.absolute().exists():
        raise Exception("Backup db was not created")
    elif (
        new_path.absolute().stat().st_size
        != (
            db_path
            or placeholder.databasePlaceholder().databasePathHelper(model_id, username)
        )
        .absolute()
        .stat()
        .st_size
    ):
        raise Exception("backup db file should be the same size")


def media_labelled_in_backups(database_path, label):
    """(media_id, model_id) of the rows saved as downloaded with media type
    `label` in the automatic backups (`user_data_copy_N.db`, `old_schema_*`)
    beside the database. The backups are only read; one that can't be read is
    skipped."""
    folder = pathlib.Path(database_path).parent / "backup"
    found = set()
    if not folder.is_dir():
        return found
    backups = sorted(
        {*folder.glob("user_data_copy_*.db"), *folder.glob("old_schema_*.db")}
    )
    for path in backups:
        # immutable: no lock, no -wal or -shm file left beside the backup
        uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
        try:
            with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
                columns = {
                    row[1] for row in conn.execute("PRAGMA table_info('medias')")
                }
                if not {"media_id", "model_id", "media_type", "downloaded"} <= columns:
                    continue
                found.update(
                    conn.execute(
                        "SELECT DISTINCT media_id, model_id FROM medias"
                        " WHERE media_type = ? AND downloaded = 1"
                        " AND media_id IS NOT NULL",
                        [label],
                    ).fetchall()
                )
        except sqlite3.Error as E:
            log.debug(f"skipped backup {path}: {E}")
    return found


def create_backup(model_id, username, backup=None, db_path=None, **kwargs):
    database_path = db_path or placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    database_copy = None
    now = arrow.now().float_timestamp
    last = cache.get(f"{username}_{model_id}_db_backup", default=now)
    if backup:
        database_copy = database_path.parent / "backup" / f"{backup}"
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        copy_path(database_path, database_copy)
    elif now - last > of_env.getattr("DBINTERVAL") and database_path.exists():
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        copy_path(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    elif (
        not pathlib.Path(database_path.parent / "backup").exists()
        or len(list(pathlib.Path(database_path.parent / "backup").iterdir())) == 0
    ):
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        copy_path(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)

    return database_copy
