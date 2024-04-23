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
    db_merger=MergeDatabase(new_db_path)
    
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
            await db_merger(ele)

        except Exception as E:
            log.error(f"Issue getting required info for {ele}")
            log.traceback_(E)
            log.traceback_(traceback.format_exc())

class MergeDatabase():
    def __init__(self,new_db_path):
         self._data_init=False
         self._new_db=new_db_path

    async def __call__(self, old_db_path):
        """
        This method is called when the object is used like a function.

        Args:
            other (int): The value to add to self.value.

        Returns:
            int: The sum of self.value and other.
        """
        await self._data_initializer()
        return await self.merge_database(old_db_path)
    async def _data_initializer(self):
        if not self._data_init:
            self._curr_labels =set(list(map(lambda x:tuple(x[key] for key in["post_id", "label_id", "model_id"] )),await get_all_labels_transition(db_path=self._new_db)))
            self._curr_medias= set(list(map(lambda x:tuple(x[key] for key in ["media_id", "model_id"] )),await get_all_medias_transition(db_path=self._new_db)))
            self._curr_posts =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_posts_transition(db_path=self._new_db)))
            self._curr_products =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_products_transition(db_path=self._new_dbh)))
            self._curr_others =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_others_transition(db_path=self._new_db)))
            self._curr_stories =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_stories_transition(db_path=self._new_db)))
            self._curr_messages =set(list(map(lambda x:tuple(x[key] for key in ["post_id", "model_id"] )),await get_all_messages_transition(db_path=self._new_db)))
            self._curr_profiles =set(list(map(lambda x:tuple(x[key] for key in ["user_id","username"] )),await get_all_profiles(db_path=self._new_db)))
            self._curr_models =set(list(map(lambda x:tuple(x[key] for key in [ "model_id"] )),await get_all_models(db_path=self._new_db)))
        self._data_init=True

    async def merge_database(self, db_path):
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
                await self.merge_media_helper(db_path)
            elif key == "labels":
                await self.merge_label_helper( db_path)
            elif key == "posts":
                await self.merge_posts_helper( db_path)
            elif key == "products":
                await self.merge_products_helper(db_path)
            elif key == "others":
                await self.merge_others_helper(db_path)
            elif key == "stories":
                await self.merge_stories_helper(db_path)
            elif key == "profiles":
                await self.merge_profiles_helper(db_path)

            elif key == "models":
                await self.merge_models_helper(db_path)
            elif key=="messages":
                await self.merge_messages_helper(db_path)



       
        
        


    async def merge_media_helper(self,old_db):
        keys = ["media_id", "model_id"]
        inserts_old_db = await get_all_medias_transition(db_path=old_db)
        await write_media_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_medias, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_medias.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_label_helper(self,old_db):
        keys = ["post_id", "label_id", "model_id"]
        inserts_old_db = await get_all_labels_transition(db_path=old_db)
        await write_labels_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_labels, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_labels.update( map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_posts_helper(self,old_db):
        keys = ["post_id", "model_id"]

        inserts_old_db = await get_all_posts_transition(db_path=old_db)
        await write_post_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_posts, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_posts.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))
        


    async def merge_products_helper(self,old_db):
        keys = ["post_id", "model_id"]
        inserts_old_db = await get_all_products_transition(db_path=old_db)
        await write_products_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_products, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_products.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_others_helper(self,old_db):
        keys = ["post_id", "model_id"]


        inserts_old_db = await get_all_others_transition(db_path=old_db)
        await write_others_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in  self._curr_others, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_others.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_stories_helper(self,old_db):
        global curr_stories
        keys = ["post_id", "model_id"]
        inserts_old_db = await get_all_stories_transition(db_path=old_db)
        await write_stories_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_stories, inserts_old_db
                )
            ),
            db_path=self._new_db,

        )

        self._curr_stories.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_profiles_helper(self,old_db):
        keys = ["user_id","username"]
        inserts_old_db = await get_all_profiles(db_path=old_db)
        await write_profile_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_profiles, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_profiles.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_models_helper(self,old_db):
        keys = ["model_id"]
        inserts_old_db = get_single_model_via_profile(db_path=old_db)
        (
            await write_models_table(
                model_id=inserts_old_db,
                db_path=self._new_db,
            )
            if inserts_old_db not in self._curr_models
            else None
        )
        self._curr_models.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))


    async def merge_messages_helper(self,old_db):
        global curr_messages
        keys = ["post_id", "model_id"]
        inserts_old_db = await get_all_messages_transition(db_path=old_db)
        await write_messages_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_messages, inserts_old_db
                )
            ),
            db_path=self._new_db,
        )
        self._curr_messages.update(map(
                    lambda x: tuple(x[key] for key in keys), inserts_old_db
                ))

