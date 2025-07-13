import logging
import copy
import arrow
import asyncio

import ofscraper.utils.settings as settings
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.data.posts.post import post_media_process
from ofscraper.commands.utils.strings import (
    metadata_activity_str,
    mark_stray_str,
)
from ofscraper.commands.utils.command import CommandManager

from ofscraper.utils.context.run_async import run as run_async
import ofscraper.db.operations as operations
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)
import ofscraper.data.api.init as init
import ofscraper.utils.actions as actions
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.commands.utils.scrape_context import scrape_context_manager
from ofscraper.main.close.final.final import final_action
from ofscraper.utils.checkers import check_auth
import ofscraper.managers.manager as manager
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.context.exit as exit


from ofscraper.commands.scraper.actions.utils.paths import setDirectoriesDate

from ofscraper.commands.scraper.actions.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
from ofscraper.commands.metadata.consumer import consumer
from ofscraper.commands.metadata.desc import desc
from ofscraper.data.posts.scrape_paid import scrape_paid_all
from ofscraper.managers.postcollection import PostCollection

log = logging.getLogger("shared")


class MetadataCommandManager(CommandManager):
    def __init__(self):
        super().__init__()

    @run_async
    async def process_users_metadata_normal(self, userdata, session):
        with progress_utils.setup_live("main_activity"):
            """Processes metadata in normal mode."""
            progress_updater.activity.update_user(
                description="Users with Updated Metadata", total=len(userdata)
            )
            await self._process_users_normal(
                userdata, session, self._execute_metadata_action_on_user
            )
        progress_updater.activity.update_task(description="Finished Metadata Mode")

    @run_async
    async def metadata_user_first(self, userdata, session):
        """Processes metadata in user-first mode."""
        # Phase 1: Gather data for all users firstprocess_users_normal
        progress_updater.activity.update_overall(visible=True, total=2)
        data = await self._gather_user_first_data(
            userdata, session, self._get_metadata_for_user
        )
        progress_updater.activity.update_user(
            description="Users with Updated Metadata", total=len(data.keys())
        )

        await self._execute_user_first_actions(
            data, self._execute_metadata_action_on_user
        )
        progress_updater.activity.update_task(description="Finished Metadata Mode")

    @run_async
    async def metadata_paid_all(self):
        """Helper to run the 'scrape_paid_all' process in metadata mode."""
        old_args = copy.deepcopy(settings.get_args())
        self._force_change_metadata()
        await scrape_paid_all()
        settings.update_args(old_args)

    def _force_change_metadata(self):
        """Helper to temporarily set the 'metadata' action for paid scraping."""
        args = settings.get_args(copy=True)
        args.metadata = args.scrape_paid
        settings.update_args(args)

    async def _execute_metadata_action_on_user(
        self,
        ele=None,
        postcollection: PostCollection = None,
    ):
        """
        The specific action for metadata processing for a single user.
        This contains the logic you wanted to fill in.
        """

        username = ele.name
        model_id = ele.id
        log.warning(
            f"Performing metadata update for [bold]{username}[/bold]\n"
            f"Subscription Active: {ele.active}"
        )

        # Ensure the user's database table exists
        await operations.table_init_create(model_id=model_id, username=username)

        # Update the progress bar description for the current user
        progress_updater.activity.update_task(
            description=metadata_activity_str.format(username=username)
        )
        media = postcollection.get_media_for_metadata()

        # Run the main metadata processing function
        await metadata_process(username, model_id, media)

        # Optionally, find and mark media in the DB that is no longer accessible
        await self._metadata_stray_media(username, model_id, media)

        # Update and print statistics for this user's metadata activity
        manager.Manager.stats_manager.update_and_print_stats(
            username, "metadata", media
        )

        # Mark this user as processed for the metadata activity
        manager.Manager.model_manager.mark_as_processed(username, activity="metadata")

    async def _get_metadata_for_user(self, c, ele):
        """
        The specific data gathering function for metadata in user-first mode.
        """
        postcollection = await post_media_process(ele, c)
        return {
            ele.id: {
                "username": ele.name,
                "ele": ele,
                "postcollection": postcollection,
                "avatar": ele.avatar,
            }
        }

    async def _metadata_stray_media(self, username, model_id, media):
        """
        Finds and marks media in the database that is no longer present in a scrape.
        """
        if not settings.get_settings().mark_stray:
            return
        all_db_media = []
        curr_media_set = set(map(lambda x: str(x.id), media))
        args = settings.get_args()
        progress_updater.activity.update_task(
            description=mark_stray_str.format(username=username)
        )
        # Fetch all media for the user from the database based on selected areas
        if "Timeline" in args.download_area:
            all_db_media.extend(
                await get_timeline_media(model_id=model_id, username=username)
            )
        if "Messages" in args.download_area:
            all_db_media.extend(
                await get_messages_media(model_id=model_id, username=username)
            )
        if "Archived" in args.download_area:
            all_db_media.extend(
                await get_archived_media(model_id=model_id, username=username)
            )
        if not all_db_media:
            return
        # Filter to find items in the DB that were not in the current scrape
        filtered_media = list(
            filter(
                lambda x: str(x["media_id"]) not in curr_media_set
                and arrow.get(x.get("posted_at") or 0).is_between(
                    arrow.get(args.after or 0), args.before
                )
                and x.get("downloaded") != 1
                and x.get("unlocked") != 0,
                all_db_media,
            )
        )
        if filtered_media:
            log.info(f"Found {len(filtered_media)} stray items to mark as locked")
            await batch_set_media_downloaded(
                filtered_media, model_id=model_id, username=username
            )

    @property
    def run_metadata(self):
        return settings.get_settings().metadata


def metadata():
    metaCommandManager = MetadataCommandManager()
    check_auth()
    with progress_utils.stop_live_screen(clear="all"):
        with progress_utils.setup_live("activity_desc", revert=True):
            if settings.get_settings().scrape_paid:
                metaCommandManager.metadata_paid_all()
            if not metaCommandManager.run_metadata:
                pass

            elif not settings.get_settings().users_first:
                userdata, session = prepare()
                metaCommandManager.process_users_metadata_normal(userdata, session)
            else:
                userdata, session = prepare()
                metaCommandManager.metadata_user_first(userdata, session)
        final_action()


@run
async def process_dicts(username, model_id, medialist):
    task1 = None
    with progress_utils.setup_live("metadata"):
        common_globals.mainProcessVariableInit()
        try:

            aws = []

            async with manager.Manager.get_metadata_session() as c:
                for ele in medialist:
                    aws.append((c, ele, model_id, username))
                task1 = progress_updater.metadata.add_overall_task(
                    desc.format(
                        p_count=0,
                        v_count=0,
                        a_count=0,
                        skipped=0,
                        mediacount=len(medialist),
                        forced_skipped=0,
                        sumcount=0,
                        total_bytes_download=0,
                        total_bytes=0,
                    ),
                    total=len(aws),
                    visible=True,
                )
                concurrency_limit = get_max_workers()
                lock = asyncio.Lock()
                consumers = [
                    asyncio.create_task(consumer(aws, task1, medialist, lock))
                    for _ in range(concurrency_limit)
                ]
                await asyncio.gather(*consumers)
        except Exception as E:
            with exit.DelayedKeyboardInterrupt():
                raise E
        finally:
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread, cache.close
            )
            common_globals.thread.shutdown()

        setDirectoriesDate()
        progress_updater.metadata.remove_overall_task(task1)


@run_async
async def metadata_process(username, model_id, medialist):
    await metadata_picker(username, model_id, medialist)


async def metadata_picker(username, model_id, medialist):
    if len(medialist) == 0:
        return
    else:
        await process_dicts(username, model_id, medialist)


def process_selected_areas():
    log.debug("[bold deep_sky_blue2] Running Metadata Mode [/bold deep_sky_blue2]")
    progress_updater.activity.update_task(description="Running Metadata Mode")
    with scrape_context_manager():
        metadata()


def prepare():
    with progress_utils.stop_live_screen(clear="all"):
        profile_tools.print_current_profile()
        actions.select_areas()
        init.print_sign_status()
        manager.Manager.stats_manager.clear_scraper_activity_stats()
        userdata = manager.Manager.model_manager.prepare_scraper_activity()
        session = manager.Manager.aget_ofsession(
            sem_count=of_env.getattr("API_REQ_SEM_MAX"),
            total_timeout=of_env.getattr("API_TIMEOUT_PER_TASK"),
        )
        return userdata, session
