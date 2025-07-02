import traceback
import time
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
    avatar_str,
    all_paid_metadata_str,
    all_paid_progress_metadata_str,
    metadata_activity_str,
    mark_stray_str,
)
from ofscraper.commands.utils.command import commmandManager
from ofscraper.data.posts.scrape_paid import (
    process_scrape_paid,
    process_user_info_printer,
    process_user,
)
from ofscraper.utils.context.run_async import run as run_async
import ofscraper.db.operations as operations
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)
from ofscraper.data.posts.post import process_areas
import ofscraper.data.api.init as init
import ofscraper.utils.actions as actions
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.commands.utils.scrape_context import scrape_context_manager
from ofscraper.main.close.final.final import final_action
from ofscraper.utils.checkers import check_auth
import ofscraper.main.manager as manager
from ofscraper.scripts.after_download_action_script import after_download_action_script
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.cache as cache
import ofscraper.utils.context.exit as exit


from ofscraper.commands.scraper.actions.utils.log import final_log, final_log_text
from ofscraper.commands.scraper.actions.utils.paths import setDirectoriesDate

from ofscraper.commands.scraper.actions.utils.workers import get_max_workers
from ofscraper.utils.context.run_async import run
from ofscraper.commands.metadata.consumer import consumer
from ofscraper.commands.metadata.desc import desc

log = logging.getLogger("shared")


class metadataCommandManager(commmandManager):
    def __init__(self):
        super().__init__()

    @run_async
    async def process_users_metadata_normal(self, userdata, session):
        user_action_funct = self._get_user_action_function(
            self._execute_metadata_action_on_user
        )
        progress_updater.update_user_activity(description="Users with Updated Metadata")
        return await user_action_funct(userdata, session)

    @run_async
    async def metadata_user_first(self, userdata, session):
        data = await self._get_userfirst_data_function(self._metadata_data_user_first)(
            userdata, session
        )
        progress_updater.update_activity_task(description="Changing Metadata for Users")
        progress_updater.update_user_activity(
            description="Users with Metadata Changed", completed=0
        )
        # pass all data to userfirst
        return await self._get_userfirst_action_execution_function(
            self._execute_metadata_action_on_user
        )(data)

    @run_async
    async def metadata_paid_all(self):
        old_args = copy.deepcopy(settings.get_args())
        self._force_change_metadata()
        out = ["[bold yellow]Scrape Paid Results[/bold yellow]"]

        async for count, value, length in process_scrape_paid():
            process_user_info_printer(
                value,
                length,
                count,
                all_paid_update=all_paid_metadata_str,
                all_paid_activity=metadata_activity_str,
                log_progress=all_paid_progress_metadata_str,
            )
            out.append(await process_user(value, length))
        settings.update_args(old_args)
        return out

    def _force_change_metadata(self):
        args = settings.get_args()
        args.metadata = args.scrape_paid
        settings.update_args(args)

    async def _execute_metadata_action_on_user(
        self, *args, ele=None, media=None, **kwargs
    ):
        username = ele.name
        model_id = ele.id
        mark_stray = settings.get_settings().mark_stray
        metadata_action = settings.get_settings().metadata
        active = ele.active
        log.warning(
            f"""
                    Perform Meta {metadata_action} with
                    Mark Stray: {mark_stray}
                    Anon Mode {settings.get_settings().anon}

                    for [bold]{username}[/bold]
                    [bold]Subscription Active:[/bold] {active}
                    """
        )
        await operations.table_init_create(model_id=model_id, username=username)
        progress_updater.update_activity_task(
            description=metadata_activity_str.format(username=username)
        )
        data = await metadata_process(username, model_id, media)
        await self._metadata_stray_media(username, model_id, media)
        return [data]

    async def _metadata_stray_media(SELF, username, model_id, media):
        if not settings.get_settings().mark_stray:
            return
        all_media = []
        curr_media_set = set(map(lambda x: str(x.id), media))
        args = settings.get_args()
        progress_updater.update_activity_task(
            description=mark_stray_str.format(username=username)
        )
        if "Timeline" in args.download_area:
            all_media.extend(
                await get_timeline_media(model_id=model_id, username=username)
            )
        if "Messages" in args.download_area:
            all_media.extend(
                await get_messages_media(model_id=model_id, username=username)
            )
        if "Archived" in args.download_area:
            all_media.extend(
                await get_archived_media(model_id=model_id, username=username)
            )
        if not bool(all_media):
            return
        filtered_media = list(
            filter(
                lambda x: str(x["media_id"]) not in curr_media_set
                and arrow.get(x.get("posted_at") or 0).is_between(
                    arrow.get(args.after or 0), args.before
                )
                and x.get("downloaded") != 1
                and x.get("unlocked") != 0,
                all_media,
            )
        )
        log.info(f"Found {len(filtered_media)} stray items to mark as locked")
        batch_set_media_downloaded(filtered_media, model_id=model_id, username=username)

    def _get_user_action_function(self, funct):
        async def wrapper(userdata, session, *args, **kwargs):
            async with session as c:
                data = ["[bold yellow]Normal Mode Results[/bold yellow]"]
                for ele in userdata:
                    username = ele.name
                    model_id = ele.id
                    try:
                        with progress_utils.setup_api_split_progress_live():
                            self._data_helper(ele)
                            postcollection = await post_media_process(ele, c=c)

                        with progress_utils.setup_activity_group_live(revert=False):
                            avatar = ele.avatar
                            if (
                                of_env.getattr("SHOW_AVATAR")
                                and avatar
                                and settings.get_settings().userfirst
                            ):
                                logging.getLogger("shared").warning(
                                    avatar_str.format(avatar=avatar)
                                )
                            data.extend(
                                await funct(
                                    media=postcollection.get_media_for_metadata(),
                                    posts=postcollection.get_posts_for_text_download(),
                                    like_posts=postcollection.get_posts_to_like(),
                                    ele=ele,
                                )
                            )
                    except Exception as e:

                        log.traceback_(f"failed with exception: {e}")
                        log.traceback_(traceback.format_exc())

                        if isinstance(e, KeyboardInterrupt):
                            raise e
                    finally:
                        progress_updater.increment_user_activity()
                progress_updater.update_activity_task(
                    description="Finished Metadata Mode"
                )
                time.sleep(1)
                return data

        return wrapper

    # data functions
    @run_async
    async def _metadata_data_user_first(self, session, ele):
        try:
            return await self._process_ele_user_first_data_retriver(
                ele=ele, session=session
            )
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            log.traceback_(f"failed with exception: {e}")
            log.traceback_(traceback.format_exc())

    async def _process_ele_user_first_data_retriver(self, ele=None, session=None):
        data = {}
        progress_utils.switch_api_progress()
        model_id = ele.id
        username = ele.name
        avatar = ele.avatar
        try:
            model_id = ele.id
            username = ele.name
            await operations.table_init_create(model_id=model_id, username=username)
            postcollection = await process_areas(ele, model_id, username, c=session)
            return {
                model_id: {
                    "username": username,
                    "media": postcollection.get_media_for_metadata(),
                    "avatar": avatar,
                    "ele": ele,
                    "posts": postcollection.get_posts_for_text_download(),
                    "like_posts": postcollection.get_posts_to_like(),
                }
            }
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            log.traceback_(f"failed with exception: {e}")
            log.traceback_(traceback.format_exc())
        return data

    @property
    def run_metadata(self):
        return settings.get_settings().metadata


def metadata():
    metaCommandManager = metadataCommandManager()
    check_auth()
    with progress_utils.setup_activity_progress_live(
        revert=True, stop=True, setup=True
    ):
        scrape_paid_data = []
        userfirst_data = []
        normal_data = []
        userdata = []
        if settings.get_settings().scrape_paid:
            scrape_paid_data = metaCommandManager.metadata_paid_all()
        if not metaCommandManager.run_metadata:
            pass

        elif not settings.get_settings().users_first:
            userdata, session = prepare()
            normal_data = metaCommandManager.process_users_metadata_normal(
                userdata, session
            )
        else:
            userdata, session = prepare()
            userfirst_data = metaCommandManager.metadata_user_first(userdata, session)
    final_action(normal_data, scrape_paid_data, userfirst_data)


@run
async def process_dicts(username, model_id, medialist):
    task1 = None
    with progress_utils.setup_metadata_progress_live():
        common_globals.mainProcessVariableInit()
        try:

            aws = []

            async with manager.Manager.get_download_session() as c:
                for ele in medialist:
                    aws.append((c, ele, model_id, username))
                task1 = progress_updater.add_metadata_task(
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
        progress_updater.remove_metadata_task(task1)
        final_log(username)
        return final_log_text(username)


@run_async
async def metadata_process(username, model_id, medialist):
    data = await metadata_picker(username, model_id, medialist)
    after_download_action_script(username, medialist,action="metadata")
    return data


async def metadata_picker(username, model_id, medialist):
    if len(medialist) == 0:
        out = final_log_text(username, 0, 0, 0, 0, 0, 0)
        logging.getLogger("shared").error(out)
        return out
    else:
        return await process_dicts(username, model_id, medialist)


def process_selected_areas():
    log.debug("[bold deep_sky_blue2] Running Metadata Mode [/bold deep_sky_blue2]")
    progress_updater.update_activity_task(description="Running Metadata Mode")
    with scrape_context_manager():
        with progress_utils.setup_activity_group_live(revert=True):
            metadata()


def prepare():
    profile_tools.print_current_profile()
    actions.select_areas()
    init.print_sign_status()
    userdata = manager.Manager.model_manager.get_selected_models(rescan=False)
    session = manager.Manager.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_SEM_MAX"),
        total_timeout=of_env.getattr("API_TIMEOUT_PER_TASK"),
    )
    return userdata, session
