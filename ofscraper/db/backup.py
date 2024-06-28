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

import logging
import pathlib

import arrow
from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
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
    elif now - last > constants.getattr("DBINTERVAL") and database_path.exists():
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
