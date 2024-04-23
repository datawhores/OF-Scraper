import logging
import pathlib
import traceback

import ofscraper.utils.paths.paths as paths
from ofscraper.db.operations import (
    create_tables,
    get_single_model_via_profile,
    modify_tables,
)
from ofscraper.db.operations_.labels import (
    get_all_labels_transition,
    write_labels_table_transition,
)
from ofscraper.db.operations_.media import (
    get_all_medias_transition,
    write_media_table_transition,
)
from ofscraper.db.operations_.others import (
    get_all_others_transition,
    get_all_products_transition,
    write_others_table_transition,
    write_products_table_transition,
)
from ofscraper.db.operations_.posts import (
    get_all_posts_transition,
    write_post_table_transition,
)
from ofscraper.db.operations_.profile import (
    get_all_models,
    get_all_profiles,
    write_models_table,
    write_profile_table_transition,
)
from ofscraper.db.operations_.stories import (
    get_all_stories_transition,
    write_stories_table_transition,
)
from ofscraper.db.operations_.messages import (
    get_all_messages_transition,
    write_messages_table_transition,
)
from ofscraper.utils.context.run_async import run


log = logging.getLogger("shared")


@run
async def batch_database_changes(new_root, old_root):
    
    if not pathlib.Path(old_root).is_dir():
        raise FileNotFoundError("Path is not dir")
    old_root=pathlib.Path(old_root) 
    new_root=pathlib.Path(new_root)
    new_root.mkdir(exist_ok=True,parents=True)
    new_db_path=new_root/"user_data.db"
    
    set_up_globals()
    await create_tables(db_path=new_db_path)
    for ele in paths.get_all_db(old_root):
        log.info(f"Merging {ele} with {new_db_path}")
        if ele == new_db_path:
            continue
        try:
            model_id = get_single_model_via_profile(db_path=ele)
            if not model_id:
                raise Exception("No model ID")
            elif not str(model_id).isnumeric():
                raise Exception("Model ID is not numeric")
            await create_tables(db_path=ele)
            await modify_tables(model_id=model_id, db_path=ele)
            await merge_database(ele, db_path=new_db_path)

        except Exception as E:
            log.error(f"Issue getting required info for {ele}")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())


async def merge_database(old_db, db_path=None):
    for key in [
        "medias",
        "labels",
        "posts",
        "products",
        "others",
        "stories",
        "profiles",
        "models",
        "messages"
    ]:
        if key == "medias":
            await merge_media_helper(old_db, db_path=db_path)
        elif key == "labels":
            await merge_label_helper(old_db, db_path=db_path)
        elif key == "posts":
            await merge_posts_helper(old_db, db_path=db_path)
        elif key == "products":
            await merge_products_helper(old_db, db_path=db_path)
        elif key == "others":
            await merge_others_helper(old_db, db_path=db_path)
        elif key == "stories":
            await merge_stories_helper(old_db, db_path=db_path)
        elif key == "profiles":
            await merge_profiles_helper(old_db, db_path=db_path)

        elif key == "models":
            await merge_models_helper(old_db, db_path=db_path)
        elif key=="messages":
            await merge_messages_helper(old_db, db_path=db_path)

async def set_up_globals(db_path=None):
    global curr_medias
    global curr_labels
    global curr_posts
    global curr_products
    global curr_others
    global curr_stories
    global curr_profiles
    global curr_models
    global curr_messages
    curr_labels= set(list(map(lambda x:tuple(x[key] for key in["post_id", "label_id", "model_id"] )),await get_all_labels_transition(db_path=db_path)))
    curr_medias= set(list(map(lambda x:tuple(x[key] for key in ["media_id", "model_id"] )),await get_all_medias_transition(db_path=db_path)))
    curr_posts =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_posts_transition(db_path=db_path)))
    curr_products =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_products_transition(db_path=db_path)))
    curr_others =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_others_transition(db_path=db_path)))
    curr_stories =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_stories_transition(db_path=db_path)))
    curr_messages =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_messages_transition(db_path=db_path)))
    curr_profiles =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_profiles(db_path=db_path)))
    curr_models =set(list(map(lambda x:tuple(x[key] for key in [ "model_id"] )),await get_all_models(db_path=db_path)))

    
    


async def merge_media_helper(old_db, db_path=None):
    keys = ["media_id", "model_id"]
    inserts_old_db = await get_all_medias_transition(db_path=old_db)
    await write_media_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_medias, inserts_old_db
            )
        ),
        db_path=db_path,
    )
    curr_medias.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_label_helper(old_db, db_path=None):
    global curr_labels
    keys = ["post_id", "label_id", "model_id"]
    inserts_old_db = await get_all_labels_transition(db_path=old_db)
    await write_labels_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_labels, inserts_old_db
            )
        ),
        db_path=db_path,
    )
    curr_labels.update( map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_posts_helper(old_db, db_path=None):
    global curr_posts
    keys = ["post_id", "model_id"]

    inserts_old_db = await get_all_posts_transition(db_path=old_db)
    await write_post_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_posts, inserts_old_db
            )
        ),
        db_path=db_path,
    )
      curr_posts.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))
    


async def merge_products_helper(old_db, db_path=None):
    global curr_products
    keys = ["post_id", "model_id"]
    inserts_old_db = await get_all_products_transition(db_path=old_db)
    await write_products_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_products, inserts_old_db
            )
        ),
        db_path=db_path,
    )
    curr_products.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_others_helper(old_db, db_path=None):
    global curr_others
    keys = ["post_id", "model_id"]


    inserts_old_db = await get_all_others_transition(db_path=old_db)
    await write_others_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in  curr_others, inserts_old_db
            )
        ),
        db_path=db_path,
    )
    curr_others.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_stories_helper(old_db, db_path=None):
    global curr_stories
    keys = ["post_id", "model_id"]
    inserts_old_db = await get_all_stories_transition(db_path=old_db)
    await write_stories_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_stories, inserts_old_db
            )
        ),
        db_path=db_path,

    )

    curr_stories.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_profiles_helper(old_db, db_path=None):
    global curr_profiles
    keys = ["user_id"]
    inserts_old_db = await get_all_profiles(db_path=old_db)
    await write_profile_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_profiles, inserts_old_db
            )
        ),
        db_path=db_path,
    )
    curr_profiles.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_models_helper(old_db, db_path=None):
    global curr_models
    keys = ["model_id"]
    inserts_old_db = get_single_model_via_profile(db_path=old_db)
    (
        await write_models_table(
            model_id=inserts_old_db,
            db_path=db_path,
        )
        if inserts_old_db not in curr_models
        else None
    )
    curr_models.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))


async def merge_messages_helper(old_db, db_path=None):
    global curr_messages
    keys = ["post_id", "model_id"]
    inserts_old_db = await get_all_messages_transition(db_path=old_db)
    await write_messages_table_transition(
        list(
            filter(
                lambda x: tuple(x[key] for key in keys) not in curr_messages, inserts_old_db
            )
        ),
        db_path=db_path,
    )
    curr_messages.update(map(
                lambda x: tuple(x[key] for key in keys), inserts_old_db
            ))

