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

from rich.console import Console

from ofscraper.db.backup import create_backup_transition, restore_backup_transition
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.labels import add_column_labels_ID, rebuild_labels_table
from ofscraper.db.operations_.media import (
    add_column_media_duration,
    add_column_media_hash,
    add_column_media_ID,
    add_column_media_posted_at,
    add_column_media_unlocked,
    rebuild_media_table,
)
from ofscraper.db.operations_.messages import (
    add_column_messages_ID,
    rebuild_messages_table,
)
from ofscraper.db.operations_.others import (
    add_column_other_ID,
    add_column_products_ID,
    add_flag_schema,
    rebuild_others_table,
    rebuild_products_table,
)
from ofscraper.db.operations_.posts import (
    add_column_post_ID,
    add_column_post_opened,
    add_column_post_pinned,
    add_column_post_stream,
    rebuild_posts_table,
)
from ofscraper.db.operations_.profile import rebuild_profiles_table
from ofscraper.db.operations_.stories import (
    add_column_stories_ID,
    rebuild_stories_table,
)
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


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


async def add_column_tables(model_id=None, username=None, db_path=None, **kwargs):
    missing = get_group_difference(
        model_id=model_id, username=username, db_path=db_path
    )
    if len(missing) == 0:
        return
    elif "media_hash" in missing:
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
    if "posts_stream" in missing:
        await add_column_post_stream(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_stream", model_id=model_id, username=username, db_path=db_path
        )

    if "posts_opened" in missing:
        await add_column_post_opened(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_opened", model_id=model_id, username=username, db_path=db_path
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
    if len(missing) == 0:
        return
    elif "profile_username_constraint_modified" in missing:
        await rebuild_profiles_table(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "profile_username_constraint_modified",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "stories_model_id_constraint_added" in missing:
        await rebuild_stories_table(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "stories_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "media_post_id_constraint_added" in missing or "media_bool_changes" in missing:
        await rebuild_media_table(model_id=model_id, username=username, db_path=db_path)
        await add_flag_schema(
            "media_post_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
        await add_flag_schema(
            "media_bool_changes",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "posts_model_id_constraint_added" in missing:
        await rebuild_posts_table(model_id=model_id, username=username, db_path=db_path)
        await add_flag_schema(
            "posts_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "others_model_id_constraint_added" in missing:
        await rebuild_others_table(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "others_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "products_model_id_constraint_added" in missing:
        await rebuild_products_table(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "products_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
    if "messages_model_id_constraint_added" in missing:
        await rebuild_messages_table(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "messages_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )

    if "labels_model_id_constraint_added" in missing:
        await rebuild_labels_table(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "labels_model_id_constraint_added",
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
