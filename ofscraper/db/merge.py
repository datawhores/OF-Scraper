import logging
import pathlib
import traceback

import ofscraper.sites as sites
import ofscraper.utils.paths.db as paths_db
from ofscraper.db.operations import create_tables
from ofscraper.db.operations_.empty import empty
from ofscraper.db.operations_.labels import (
    get_all_labels_transition,
    write_labels_table_transition,
)
from ofscraper.db.operations_.media import (
    get_all_medias_transition,
    update_media_table_download_transition,
    write_media_table_transition,
)
from ofscraper.db.operations_.messages import (
    get_all_messages_transition,
    write_messages_table_transition,
)
from ofscraper.db.operations_.others import (
    get_all_others_transition,
    get_all_products_transition,
    get_site_flag,
    write_others_table_transition,
    write_products_table_transition,
    write_site_flag,
)
from ofscraper.db.operations_.posts import (
    get_all_posts_transition,
    write_post_table_transition,
)
from ofscraper.db.operations_.profile import (
    get_all_models,
    get_all_profiles,
    get_single_model_via_profile,
    write_models_table,
    write_profile_table_transition,
)
from ofscraper.db.operations_.stories import (
    get_all_stories_transition,
    write_stories_table_transition,
)
from ofscraper.db.transition import modify_tables

log = logging.getLogger("shared")

# Fansly ids are 18-digit numbers; OnlyFans ids are far shorter
FANSLY_IDS_FROM = 10**15


class MergeDatabase:
    def __init__(self):
        self._data_init = False
        self._media_keys = ["media_id", "model_id"]
        self._media_row_keys = ["media_id", "model_id", "post_id"]
        self._label_keys = ["post_id", "label_id", "model_id"]
        self._common_key = ["post_id", "model_id"]
        self._profile_key = ["user_id", "username"]
        self._model_key = "model_id"

    async def __call__(self, old_db_folder, new_db_path):
        """
        This method is called when the object is used like a function.
        """
        # check the source before anything is created or backed up in the target
        if not pathlib.Path(old_db_folder).is_dir():
            raise FileNotFoundError(f"Merge source folder not found: {old_db_folder}")
        self._new_db = self.get_new_db(new_db_path)
        self._old_db_folder = old_db_folder
        await self._data_initializer()
        return await self.merge_database()

    def get_new_db(self, new_db_path):
        new_db_path = pathlib.Path(new_db_path)
        if new_db_path.name == "user_data.db":
            return new_db_path
        elif new_db_path.suffix == "":
            return pathlib.Path(new_db_path, "user_data.db")
        else:
            return pathlib.Path(pathlib.Path(new_db_path).parent, "user_data.db")

    async def _data_initializer(self):
        if not self._data_init:
            new_db = not self._new_db.exists()
            await create_tables(db_path=self._new_db)
            await modify_tables(db_path=self._new_db, new_db=new_db)
            # the site the merged database is for. One with nothing in it,
            # and no site recorded, takes the site of the first one merged
            self._site = await self._site_of(self._new_db)
            self._site_recorded = get_site_flag(db_path=self._new_db) is not None
            self._site_open = not self._site_recorded and await self._nothing_in(
                self._new_db
            )
            self._curr_labels = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._label_keys),
                        await get_all_labels_transition(db_path=self._new_db),
                    )
                )
            )
            curr_medias = await get_all_medias_transition(db_path=self._new_db)
            self._curr_medias = set(map(self._media_row_key, curr_medias))
            self._downloaded_medias = {}
            for x in curr_medias:
                if x["downloaded"]:
                    self._downloaded_medias.setdefault(self._media_key(x), x)
            self._curr_posts = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._common_key),
                        await get_all_posts_transition(db_path=self._new_db),
                    )
                )
            )
            self._curr_products = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._common_key),
                        await get_all_products_transition(db_path=self._new_db),
                    )
                )
            )
            self._curr_others = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._common_key),
                        await get_all_others_transition(db_path=self._new_db),
                    )
                )
            )
            self._curr_stories = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._common_key),
                        await get_all_stories_transition(db_path=self._new_db),
                    )
                )
            )
            self._curr_messages = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._common_key),
                        await get_all_messages_transition(db_path=self._new_db),
                    )
                )
            )
            self._curr_profiles = set(
                list(
                    map(
                        lambda x: tuple(x[key] for key in self._profile_key),
                        await get_all_profiles(db_path=self._new_db),
                    )
                )
            )
            self._curr_models = set(
                list(
                    map(
                        lambda x: x[self._model_key],
                        await get_all_models(db_path=self._new_db),
                    )
                )
            )
        self._data_init = True

    async def merge_database(self):
        old_root_folder = pathlib.Path(self._old_db_folder)
        new_db_path = pathlib.Path(self._new_db)
        new_db_path.parent.mkdir(exist_ok=True, parents=True)
        failures = {}
        success = {}
        empty_list = []
        for ele in paths_db.get_all_db(old_root_folder):
            if ele == new_db_path:
                continue
            log.info(f"Merging {new_db_path} with {ele}")
            try:
                await create_tables(db_path=ele)
                if await empty(db_path=ele):
                    empty_list.append(
                        {"path": str(ele), "message": "skipped because table was empty"}
                    )
                    continue
                model_id = get_single_model_via_profile(db_path=ele)
                if not model_id:
                    raise Exception("Not exactly one model_id in profile table")
                elif not str(model_id).isnumeric():
                    raise Exception("Found model_id was not numeric")
                await modify_tables(model_id=model_id, db_path=ele)
                site = await self._check_site(ele)
                try:
                    await self.merge_individual(ele)
                finally:
                    await self._keep_site(site)
                success.update(
                    {
                        model_id: {
                            "path": str(ele),
                            "model_id": model_id,
                            "message": "merge success",
                        }
                    }
                )

            except Exception as E:
                failures.update({ele: {"path": str(ele), "reason": E}})
                log.info(f"Issue getting required info for {ele}")
                log.traceback_(E)
                log.traceback_(traceback.format_exc())
        log.info(
            "\n\n\n".join(
                list(
                    map(
                        lambda x: str([(key, value) for key, value in x.items()]),
                        failures.values(),
                    )
                )
            )
        )
        return list(failures.items()), list(success.items()), empty_list

    async def _site_of(self, db_path):
        """The site a database is for. Only a site other than OnlyFans is
        recorded in one, and a Fansly database merged by a version before
        this record was kept has none: that one is told by its creators'
        ids, which are far longer than any OnlyFans id."""
        recorded = get_site_flag(db_path=db_path)
        if recorded:
            return str(recorded).lower()
        ids = [
            str(profile["user_id"])
            for profile in await get_all_profiles(db_path=db_path) or []
        ]
        if ids and all(
            id.isdecimal() and int(id) >= FANSLY_IDS_FROM for id in ids
        ):
            return sites.FANSLY
        return sites.DEFAULT_SITE

    async def _nothing_in(self, db_path):
        """True for a database with no rows and no creator."""
        return await empty(db_path=db_path) and not await get_all_profiles(
            db_path=db_path
        )

    async def _check_site(self, db_path):
        """The site of a database about to be merged. One for another site
        than the merged database's is refused: the rows don't say which site
        they are from, and the two sites' ids would be taken for each
        other's."""
        site = await self._site_of(db_path)
        if not self._site_open and site != self._site:
            raise Exception(
                f"It is for {sites.SITE_NAMES.get(site, site)}, and the"
                f" merged database is for {sites.SITE_NAMES.get(self._site, self._site)}"
            )
        return site

    async def _keep_site(self, site):
        """After a database for `site` was merged, or its merge failed part
        way: the merged database is for that site from now on, and says so.
        One that still has nothing in it stays open to either site."""
        if self._site_open:
            if await self._nothing_in(self._new_db):
                return
            self._site, self._site_open = site, False
        if self._site != sites.DEFAULT_SITE and not self._site_recorded:
            await write_site_flag(self._site, db_path=self._new_db)
            self._site_recorded = True

    async def merge_individual(self, db_path):
        await self.merge_media_helper(db_path)
        await self.merge_label_helper(db_path)
        await self.merge_posts_helper(db_path)
        await self.merge_products_helper(db_path)
        await self.merge_others_helper(db_path)
        await self.merge_stories_helper(db_path)
        await self.merge_profiles_helper(db_path)
        await self.merge_models_helper(db_path)
        await self.merge_messages_helper(db_path)

    def _media_key(self, media):
        return tuple(media[key] for key in self._media_keys)

    def _media_row_key(self, media):
        return tuple(media[key] for key in self._media_row_keys)

    async def merge_media_helper(self, old_db):
        inserts_old_db = await get_all_medias_transition(db_path=old_db)
        # one row per media item per post
        new_rows = [
            x for x in inserts_old_db if self._media_row_key(x) not in self._curr_medias
        ]
        # downloaded is per media item, as in the app's own download update:
        # the first downloaded copy wins and is written to all the item's rows,
        # including rows added for another post
        changed = set(map(self._media_key, new_rows))
        new_downloads = {}
        for x in inserts_old_db:
            key = self._media_key(x)
            if x["downloaded"] and key not in self._downloaded_medias:
                new_downloads.setdefault(key, x)
                changed.add(key)
        downloads = {**new_downloads, **self._downloaded_medias}
        await write_media_table_transition(new_rows, db_path=self._new_db)
        await update_media_table_download_transition(
            [downloads[key] for key in changed if key in downloads],
            db_path=self._new_db,
        )
        # remember this source only once its writes succeeded
        self._curr_medias.update(map(self._media_row_key, inserts_old_db))
        self._downloaded_medias.update(new_downloads)

    async def merge_label_helper(self, old_db):
        keys = self._label_keys
        inserts_old_db = await get_all_labels_transition(db_path=old_db)
        await write_labels_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_labels,
                    inserts_old_db,
                )
            ),
            db_path=self._new_db,
        )
        self._curr_labels.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )

    async def merge_posts_helper(self, old_db):
        keys = self._common_key

        inserts_old_db = await get_all_posts_transition(db_path=old_db)
        await write_post_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_posts,
                    inserts_old_db,
                )
            ),
            db_path=self._new_db,
        )
        self._curr_posts.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )

    async def merge_products_helper(self, old_db):
        keys = self._common_key
        inserts_old_db = await get_all_products_transition(db_path=old_db)
        await write_products_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_products,
                    inserts_old_db,
                )
            ),
            db_path=self._new_db,
        )
        self._curr_products.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )

    async def merge_others_helper(self, old_db):
        keys = self._common_key

        inserts_old_db = await get_all_others_transition(db_path=old_db)
        await write_others_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_others,
                    inserts_old_db,
                )
            ),
            db_path=self._new_db,
        )
        self._curr_others.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )

    async def merge_stories_helper(self, old_db):
        global curr_stories
        keys = self._common_key
        inserts_old_db = await get_all_stories_transition(db_path=old_db)
        await write_stories_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_stories,
                    inserts_old_db,
                )
            ),
            db_path=self._new_db,
        )

        self._curr_stories.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )

    async def merge_profiles_helper(self, old_db):
        keys = self._profile_key
        inserts_old_db = await get_all_profiles(db_path=old_db)
        # every name, also the ones the merged database has: such a name
        # keeps its row there, and gets the dates of both
        await write_profile_table_transition(inserts_old_db, db_path=self._new_db)
        self._curr_profiles.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )

    async def merge_models_helper(self, old_db):
        inserts_old_db = get_single_model_via_profile(db_path=old_db)
        (
            await write_models_table(
                model_id=inserts_old_db,
                db_path=self._new_db,
            )
            if inserts_old_db not in self._curr_models
            else None
        )
        self._curr_models.add(inserts_old_db)

    async def merge_messages_helper(self, old_db):
        keys = self._common_key
        inserts_old_db = await get_all_messages_transition(db_path=old_db)
        await write_messages_table_transition(
            list(
                filter(
                    lambda x: tuple(x[key] for key in keys) not in self._curr_messages,
                    inserts_old_db,
                )
            ),
            db_path=self._new_db,
        )
        self._curr_messages.update(
            map(lambda x: tuple(x[key] for key in keys), inserts_old_db)
        )
