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

import ofscraper.classes.placeholder as placeholder
from ofscraper.db.backup import (
    create_backup_transition,
    media_labelled_in_backups,
    restore_backup_transition,
)
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.labels import add_column_labels_ID, rebuild_labels_table
from ofscraper.db.operations_.media import (
    SIZE_SKIP_LABEL,
    SIZE_SKIP_REPAIR_FLAG,
    add_column_media_duration,
    add_column_media_hash,
    add_column_media_ID,
    add_column_media_posted_at,
    add_column_media_skip_permanent,
    add_column_media_unlocked,
    rebuild_media_table,
    repair_size_skipped_media,
)
from ofscraper.db.operations_.messages import (
    add_column_messages_ID,
    rebuild_messages_table,
    add_column_message_is_deleted,
    add_column_message_group_id,
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
    add_column_post_is_deleted,
    add_column_post_purchase_type,
    add_column_post_mentions,
)
from ofscraper.db.operations_.profile import rebuild_profiles_table
from ofscraper.db.operations_.stories import (
    add_column_stories_ID,
    rebuild_stories_table,
)
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


def size_skip_labels_in_backups(model_id=None, username=None, db_path=None):
    """The media the backups list as saved by the size-skip bug, while the
    repair is still to run. Read it before any backup is written: a new copy
    can replace the one that still has the label."""
    if SIZE_SKIP_REPAIR_FLAG not in get_group_difference(
        model_id=model_id, username=username, db_path=db_path
    ):
        return set()
    database = db_path or placeholder.databasePlaceholder().databasePathHelper(
        model_id, username
    )
    return media_labelled_in_backups(database, SIZE_SKIP_LABEL)


@run
async def modify_tables(
    model_id=None,
    username=None,
    db_path=None,
    new_db=False,
    backup_labels=None,
    **kwargs,
):
    if backup_labels is None:
        backup_labels = size_skip_labels_in_backups(
            model_id=model_id, username=username, db_path=db_path
        )
    # a database created just now has no older layout worth backing up
    backup = (
        None if new_db else create_backup_transition(model_id, username, db_path=db_path)
    )
    try:
        await add_column_tables(model_id=model_id, username=username, db_path=db_path)
        await modify_tables_constraints_and_columns(
            model_id=model_id, username=username, db_path=db_path
        )
        await repair_tables(
            model_id=model_id,
            username=username,
            db_path=db_path,
            backup_labels=backup_labels,
        )
    except Exception as E:
        if backup:
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
    if "posts_is_deleted" in missing:
        await add_column_post_is_deleted(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_is_deleted", model_id=model_id, username=username, db_path=db_path
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
    if "messages_is_deleted" in missing:
        await add_column_message_is_deleted(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "messages_is_deleted", model_id=model_id, username=username, db_path=db_path
        )
    if "posts_purchase_type" in missing:
        await add_column_post_purchase_type(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_purchase_type", model_id=model_id, username=username, db_path=db_path
        )
    if "posts_mentions" in missing:
        await add_column_post_mentions(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "posts_mentions", model_id=model_id, username=username, db_path=db_path
        )
    if "messages_group_id" in missing:
        await add_column_message_group_id(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "messages_group_id", model_id=model_id, username=username, db_path=db_path
        )
    if "media_skip_permanent" in missing:
        await add_column_media_skip_permanent(
            model_id=model_id, username=username, db_path=db_path
        )
        await add_flag_schema(
            "media_skip_permanent", model_id=model_id, username=username, db_path=db_path
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


async def repair_tables(
    model_id=None, username=None, db_path=None, backup_labels=None, **kwargs
):
    missing = get_group_difference(
        model_id=model_id, username=username, db_path=db_path
    )
    if SIZE_SKIP_REPAIR_FLAG in missing:
        # files a size limit skipped before #326 were saved as downloaded (#352)
        database = db_path or placeholder.databasePlaceholder().databasePathHelper(
            model_id, username
        )
        if backup_labels is None:
            backup_labels = media_labelled_in_backups(database, SIZE_SKIP_LABEL)
        changed = await repair_size_skipped_media(
            backup_labels,
            model_id=model_id,
            username=username,
            db_path=db_path,
        )
        if changed:
            log.info(
                f"set {changed} media rows saved as downloaded by a size limit back"
                f" to not downloaded in {database}; the backup folder beside it"
                " has the earlier copy"
            )
