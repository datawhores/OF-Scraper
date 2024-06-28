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

import ofscraper.classes.labels as labels
from ofscraper.db.backup import create_backup
from ofscraper.db.operations_.labels import (
    create_labels_table,
    make_label_table_changes,
)
from ofscraper.db.operations_.media import create_media_table
from ofscraper.db.operations_.messages import (
    create_message_table,
    make_messages_table_changes,
)
from ofscraper.db.operations_.others import (
    create_others_table,
    create_products_table,
    create_schema_table,
)
from ofscraper.db.operations_.posts import create_post_table, make_post_table_changes
from ofscraper.db.operations_.profile import (
    create_models_table,
    create_profile_table,
    write_models_table,
    write_profile_table,
)
from ofscraper.db.operations_.stories import (
    create_stories_table,
    make_stories_table_changes,
)
from ofscraper.db.transition import modify_tables
from ofscraper.utils.context.run_async import run

console = Console()
log = logging.getLogger("shared")


@run
async def make_changes_to_content_tables(posts, model_id, username, **kwargs):
    await make_post_table_changes(
        filter(
            lambda x: x.responsetype in {"timeline", "pinned", "archived", "streams"},
            posts,
        ),
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
async def table_init_create(model_id=None, username=None, **kwargs):
    await create_tables(model_id=model_id, username=username)
    create_backup(model_id, username)
    await modify_tables(model_id, username)
    await write_profile_table(model_id=model_id, username=username)
    await write_models_table(model_id=model_id, username=username)
