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
import shutil

import arrow
from rich.console import Console

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
from ofscraper.db.operations_.labels import *
from ofscraper.db.operations_.media import *
from ofscraper.db.operations_.messages import *
from ofscraper.db.operations_.others import *
from ofscraper.db.operations_.posts import *
from ofscraper.db.operations_.profile import *
from ofscraper.db.operations_.stories import *
from ofscraper.utils.context.run_async import run


console = Console()
log = logging.getLogger("shared")

async def create_tables(model_id, username):
    await create_models_table(model_id=model_id, username=username)
    await create_profile_table(model_id=model_id, username=username)
    await create_post_table(model_id=model_id, username=username)
    await create_message_table(model_id=model_id, username=username)
    await create_media_table(model_id=model_id, username=username)
    await create_products_table(model_id=model_id, username=username)
    await create_others_table(model_id=model_id, username=username)
    await create_stories_table(model_id=model_id, username=username)
    await create_labels_table(model_id=model_id, username=username)
    await create_schema_table(model_id=model_id, username=username)

async def modify_tables(model_id=None, username=None):
    create_backup_transition(model_id, username)
    await add_column_tables(model_id=model_id, username=username)
    await modify_tables_constraints_and_columns(model_id=model_id, username=username)


def create_backup_transition(model_id, username):
    changes = get_schema_changes(model_id=model_id, username=username)
    groupA = [
        "media_hash",
        "media_model_id",
        "post_model_id",
        "products_model_id",
        "other_model_id",
        "stories_model_id",
        "messages_model_id",
        "labels_model_id",
    ]
    groupB = [
        "profile_username_constraint_removed",
        "stories_model_id_constraint_added",
        "media_model_id_constraint_added",
        "labels_model_id_constraint_added",
        "posts_model_id_constraint_added",
        "others_model_id_constraint_added",
        "products_model_id_constraint_added",
        "messages_model_id_constraint_added",
    ]
    if len(changes) == 0:
        None
    elif not any(groupA):
        None
    elif not any(groupB):
        None
    elif len(set(groupA + groupB)) != len(changes):
        None
    else:
        return
    # action if 1 test passes
    log.info("creating a backup before transition")
    new_path = create_backup(model_id, username, "old_schema_db_backup.db")
    log.info(f"transition backup created at {new_path}")
    check_backup(model_id, username, new_path)


async def add_column_tables(model_id=None, username=None):
    changes = get_schema_changes(model_id=model_id, username=username)
    if not "media_hash" in changes:
        await add_column_media_hash(model_id=model_id, username=username)
        await add_flag_schema("media_hash", model_id=model_id, username=username)
    if not "media_model_id" in changes:
        await add_column_media_ID(model_id=model_id, username=username)
        await add_flag_schema("media_model_id", model_id=model_id, username=username)
    if not "posts_model_id" in changes:
        await add_column_post_ID(model_id=model_id, username=username)
        await add_flag_schema("posts_model_id", model_id=model_id, username=username)
    if not "products_model_id" in changes:
        await add_column_products_ID(model_id=model_id, username=username)
        await add_flag_schema("products_model_id", model_id=model_id, username=username)
    if not "other_model_id" in changes:
        await add_column_other_ID(model_id=model_id, username=username)
        await add_flag_schema("other_model_id", model_id=model_id, username=username)
    if not "stories_model_id" in changes:
        await add_column_stories_ID(model_id=model_id, username=username)
        await add_flag_schema("stories_model_id", model_id=model_id, username=username)
    if not "messages_model_id" in changes:
        await add_column_messages_ID(model_id=model_id, username=username)
        await add_flag_schema("messages_model_id", model_id=model_id, username=username)
    if not "labels_model_id" in changes:
        await add_column_labels_ID(model_id=model_id, username=username)
        await add_flag_schema("labels_model_id", model_id=model_id, username=username)


async def modify_tables_constraints_and_columns(model_id=None, username=None):
    changes = get_schema_changes(model_id=model_id, username=username)
    if not "profile_username_constraint_removed" in changes:
        await remove_unique_constriant_profile(model_id=model_id, username=username)
        await add_flag_schema(
            "profile_username_constraint_removed", model_id=model_id, username=username
        )
    if not "stories_model_id_constraint_added" in changes:
        await modify_unique_constriant_stories(model_id=model_id, username=username)
        await add_flag_schema(
            "stories_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "media_model_id_constraint_added" in changes:
        await modify_unique_constriant_media(model_id=model_id, username=username)
        await add_flag_schema(
            "media_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "posts_model_id_constraint_added" in changes:
        await modify_unique_constriant_posts(model_id=model_id, username=username)
        await add_flag_schema(
            "posts_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "others_model_id_constraint_added" in changes:
        await modify_unique_constriant_others(model_id=model_id, username=username)
        await add_flag_schema(
            "others_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "products_model_id_constraint_added" in changes:
        await modify_unique_constriant_products(model_id=model_id, username=username)
        await add_flag_schema(
            "products_model_id_constraint_added", model_id=model_id, username=username
        )
    if not "messages_model_id_constraint_added" in changes:
        await modify_unique_constriant_messages(model_id=model_id, username=username)
        await add_flag_schema(
            "messages_model_id_constraint_added", model_id=model_id, username=username
        )

    if not "labels_model_id_constraint_added" in changes:
        await modify_unique_constriant_labels(model_id=model_id, username=username)
        await add_flag_schema(
            "labels_model_id_constraint_added", model_id=model_id, username=username
        )


def check_backup(model_id, username, new_path):
    if not new_path.absolute().exists():
        raise Exception("Backup db was not created")
    elif (
        new_path.absolute().stat().st_size
        != placeholder.databasePlaceholder()
        .databasePathHelper(model_id, username)
        .absolute()
        .stat()
        .st_size
    ):
        raise Exception("backup db file should be the same size")


def create_backup(model_id, username, backup=None):
    database_path = placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    database_copy = None
    now = arrow.now().float_timestamp
    last = cache.get(f"{username}_{model_id}_db_backup", default=now)
    if backup:
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        database_copy = database_copy.parent / backup
        shutil.copy2(database_path, database_copy)
    elif now - last > constants.getattr("DBINTERVAL") and database_path.exists():
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    elif (
        not pathlib.Path(database_path.parent / "backup").exists()
        or len(list(pathlib.Path(database_path.parent / "backup").iterdir())) == 0
    ):
        database_copy = placeholder.databasePlaceholder().databasePathCopyHelper(
            model_id, username
        )
        database_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, database_copy)
        cache.set(f"{username}_{model_id}_db_backup", now)
    cache.close()
    return database_copy

@run
async def table_init_create(model_id=None, username=None):
    await create_tables(model_id=model_id, username=username)
    create_backup(model_id, username)
    # await modify_tables(model_id, username)
    # await write_profile_table(model_id=model_id, username=username)
    # await write_models_table(model_id=model_id, username=username)
