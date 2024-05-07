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

import ofscraper.classes.labels as labels
import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
from ofscraper.db.operations_.labels import (
    add_column_labels_ID,
    create_labels_table,
    make_label_table_changes,
    modify_unique_constriant_labels,
)
from ofscraper.db.operations_.media import (
    add_column_media_duration,
    add_column_media_hash,
    add_column_media_ID,
    add_column_media_posted_at,
    add_column_media_unlocked,
    create_media_table,
    modify_unique_constriant_media,
)
from ofscraper.db.operations_.messages import (
    add_column_messages_ID,
    create_message_table,
    make_messages_table_changes,
    modify_unique_constriant_messages,
)
from ofscraper.db.operations_.others import (
    add_column_other_ID,
    add_column_products_ID,
    add_flag_schema,
    create_others_table,
    create_products_table,
    create_schema_table,
    get_schema_changes,
    modify_unique_constriant_others,
    modify_unique_constriant_products,
)
from ofscraper.db.operations_.posts import (
    add_column_post_ID,
    add_column_post_pinned,
    create_post_table,
    make_post_table_changes,
    modify_unique_constriant_posts,
)
from ofscraper.db.operations_.profile import (
    create_models_table,
    create_profile_table,
    modify_unique_constriant_profile,
    write_models_table,
    write_profile_table,
)
from ofscraper.db.operations_.stories import (
    add_column_stories_ID,
    create_stories_table,
    make_stories_table_changes,
    modify_unique_constriant_stories,
)
from ofscraper.utils.context.run_async import run
from ofscraper.utils.paths.manage import copy_path

console = Console()
log = logging.getLogger("shared")


@run
async def create_tables(model_id=None, username=None, db_path=None, **kwargs):
    await create_models_table(model_id=model_id, username=username, db_path=db_path)
    await create_profile_table(model_id=model_id, username=username, db_path=db_path)
    await create_post_table(model_id=model_id, username=username, db_path=db_path)
    await create_message_table(model_id=model_id, username=username, db_path=db_path)
    await create_media_table(model_id=model_id, username=username, db_path=db_path)
    await create_products_table(model_id=model_id, username=username, db_path=db_path)
    await create_others_table(model_id=model_id, username=username, db_path=db_path)
    await create_stories_table(model_id=model_id, username=username, db_path=db_path)
    await create_labels_table(model_id=model_id, username=username, db_path=db_path)
    await create_schema_table(model_id=model_id, username=username, db_path=db_path)


@run
async def make_changes_to_content_tables(posts, model_id, username, **kwargs):
    await make_post_table_changes(
        filter(lambda x: x.responsetype in {"timeline", "pinned", "archived"}, posts),
        model_id=model_id,
        username=username,
    )
    await make_messages_table_changes(
        filter(lambda x: x.responsetype == "message", posts),
        model_id=model_id,
        username=username,
    )
    await make_stories_table_changes(
        filter(lambda x: x.responsetype in {"stories", "highlights"}, posts),
        model_id=model_id,
        username=username,
    )
    await make_label_table_changes(
        filter(lambda x: isinstance(x, labels.Label), posts), model_id, username
    )


@run
async def modify_tables(model_id=None, username=None, db_path=None, **kwargs):
    backup = create_backup_transition(model_id, username, db_path=db_path)
    try:
        await add_column_tables(model_id=model_id, username=username, db_path=db_path)
        await modify_tables_constraints_and_columns(
            model_id=model_id, username=username, db_path=db_path
        )
    except Exception as E:
        restore_backup_transition(backup, model_id, username, db_path=db_path)
        raise E


def restore_backup_transition(backup, model_id, username, db_path=None, **kwargs):
    database = db_path or placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    copy_path(backup, database)
    log.debug(f"restored {database} from {backup}")


def get_group_difference(model_id=None, username=None, db_path=None):

    changes = get_schema_changes(model_id=model_id, username=username, db_path=db_path)
    groupA = [
        "media_hash",
        "media_model_id",
        "posts_model_id",
        "posts_pinned",
        "products_model_id",
        "other_model_id",
        "stories_model_id",
        "messages_model_id",
        "labels_model_id",
        "media_posted_at",
        "media_unlocked",
        "media_duration",
    ]

    groupB = [
        "profile_username_constraint_modified",
        "stories_model_id_constraint_added",
        "media_model_id_constraint_added",
        "labels_model_id_constraint_added",
        "posts_model_id_constraint_added",
        "others_model_id_constraint_added",
        "products_model_id_constraint_added",
        "messages_model_id_constraint_added",
    ]
    return set((groupA + groupB)).difference(set(changes))


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


async def add_column_tables(model_id=None, username=None, db_path=None, **kwargs):
    missing = get_group_difference(
        model_id=model_id, username=username, db_path=db_path
    )
    if "media_hash" in missing:
        await add_column_media_hash(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "media_hash", model_id=model_id, username=username, db_path=db_path
        )
    if "media_model_id" in missing:
        await add_column_media_ID(model_id=model_id, username=username, db_path=db_path)
        await add_flag_schema(
            "media_model_id", model_id=model_id, username=username, db_path=db_path
        )
    if "media_posted_at" in missing:
        await add_column_media_posted_at(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "media_posted_at", model_id=model_id, username=username, db_path=db_path
        )
    if "media_duration" in missing:
        await add_column_media_duration(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "media_duration", model_id=model_id, username=username, db_path=db_path
        )
    if "media_unlocked" in missing:
        await add_column_media_unlocked(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "media_unlocked", model_id=model_id, username=username, db_path=db_path
        )
    if "posts_pinned" in missing:
        await add_column_post_pinned(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_pinned", model_id=model_id, username=username, db_path=db_path
        )
    if "posts_model_id" in missing:
        await add_column_post_ID(model_id=model_id, username=username, db_path=db_path)
        await add_flag_schema(
            "posts_model_id", model_id=model_id, username=username, db_path=db_path
        )
    if "products_model_id" in missing:
        await add_column_products_ID(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "products_model_id", model_id=model_id, username=username, db_path=db_path
        )
    if "other_model_id" in missing:
        await add_column_other_ID(model_id=model_id, username=username, db_path=db_path)
        await add_flag_schema(
            "other_model_id", model_id=model_id, username=username, db_path=db_path
        )
    if "stories_model_id" in missing:
        await add_column_stories_ID(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "stories_model_id", model_id=model_id, username=username, db_path=db_path
        )
    if "messages_model_id" in missing:
        await add_column_messages_ID(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "messages_model_id", model_id=model_id, username=username, db_path=db_path
        )
    if "labels_model_id" in missing:
        await add_column_labels_ID(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "labels_model_id", model_id=model_id, username=username, db_path=db_path
        )


async def modify_tables_constraints_and_columns(
    model_id=None, username=None, db_path=None, **kwargs
):
    missing = get_group_difference(
        model_id=model_id, username=username, db_path=db_path
    )
    if "profile_username_constraint_modified" in missing:
        await modify_unique_constriant_profile(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "profile_username_constraint_modified",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "stories_model_id_constraint_added" in missing:
        await modify_unique_constriant_stories(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "stories_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "media_model_id_constraint_added" in missing:
        await modify_unique_constriant_media(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "media_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "posts_model_id_constraint_added" in missing:
        await modify_unique_constriant_posts(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "others_model_id_constraint_added" in missing:
        await modify_unique_constriant_others(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "others_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "products_model_id_constraint_added" in missing:
        await modify_unique_constriant_products(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "products_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "messages_model_id_constraint_added" in missing:
        await modify_unique_constriant_messages(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "messages_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )

    if "labels_model_id_constraint_added" in missing:
        await modify_unique_constriant_labels(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "labels_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )


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
    cache.close()
    return database_copy


@run
async def table_init_create(model_id=None, username=None, **kwargs):
    await create_tables(model_id=model_id, username=username)
    create_backup(model_id, username)
    await modify_tables(model_id, username)
    await write_profile_table(model_id=model_id, username=username)
    await write_models_table(model_id=model_id, username=username)
