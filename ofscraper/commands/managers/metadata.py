

import traceback
import time
import  logging
import copy
import arrow

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.args.mutators.write as write_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.content.post import post_media_process
from ofscraper.commands.utils.strings import avatar_str, all_paid_metadata_str,all_paid_progress_metadata_str,metadata_activity_str,mark_stray_str
import ofscraper.filters.media.main as filters
from ofscraper.commands.managers.manager import commmandManager
from ofscraper.content.scrape_paid import process_scrape_paid,process_user_info_printer,process_user
from ofscraper.utils.context.run_async import run as run_async
import ofscraper.db.operations as operations
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)
from ofscraper.actions.actions.metadata.metadata import  metadata_process

log = logging.getLogger("shared")



class metadataManager(commmandManager):
    def __init__(self,user_action=None,user_first_data=None,user_first_execution=None):
        user_action=self._execute_metadata_action_on_user
        super().__init__(self,user_action=user_action,user_first_data=user_first_data,user_first_execution=user_first_execution)
    def get_user_action_function(self):
        if not self.user_action:
            return
        async def wrapper(userdata, session, *args, **kwargs):
            async with session as c:
                data = ["[bold yellow]Normal Mode Results[/bold yellow]"]
                for ele in userdata:
                    username=ele.name
                    model_id = ele.id
                    try:
                        with progress_utils.setup_api_split_progress_live():
                            self.data_helper(ele)
                            all_media, posts, like_posts = await post_media_process(
                                ele, c=c
                            )
                            all_media = filters.filtermediaFinal(
                                all_media, username, model_id
                            )
                        with progress_utils.setup_activity_group_live(revert=False):
                            avatar = ele.avatar
                            if (
                                constants.getattr("SHOW_AVATAR")
                                and avatar
                                and read_args.retriveArgs().userfirst
                            ):
                                logging.getLogger("shared_other").warning(
                                    avatar_str.format(avatar=avatar)
                                )
                            data.extend(
                                await self.user_action(
                                    media=all_media,
                                    posts=posts,
                                    like_posts=like_posts,
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
                progress_updater.update_activity_task(description="Finished Metadata Mode")
                time.sleep(1)
                return data

        return wrapper

    @run_async
    async def metadata_paid_all(self):
        old_args = copy.deepcopy(read_args.retriveArgs())
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
        write_args.setArgs(old_args)
        return out
    def _force_change_metadata(self):
        args = read_args.retriveArgs()
        args.metadata = args.scrape_paid
        write_args.setArgs(args)
    async def _execute_metadata_action_on_user(self,*args, ele=None, media=None, **kwargs):
        username = ele.name
        model_id = ele.id
        mark_stray = read_args.retriveArgs().mark_stray
        metadata_action = read_args.retriveArgs().metadata
        active = ele.active
        log.warning(
            f"""
                    Perform Meta {metadata_action} with
                    Mark Stray: {mark_stray}
                    Anon Mode {read_args.retriveArgs().anon}

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


    async def _metadata_stray_media(SELF,username, model_id, media):
        if not read_args.retriveArgs().mark_stray:
            return
        all_media = []
        curr_media_set = set(map(lambda x: str(x.id), media))
        args = read_args.retriveArgs()
        progress_updater.update_activity_task(
            description=mark_stray_str.format(username=username)
        )
        if "Timeline" in args.download_area:
            all_media.extend(await get_timeline_media(model_id=model_id, username=username))
        if "Messages" in args.download_area:
            all_media.extend(await get_messages_media(model_id=model_id, username=username))
        if "Archived" in args.download_area:
            all_media.extend(await get_archived_media(model_id=model_id, username=username))
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


        


    @property
    def run_metadata():
        return read_args.retriveArgs().metadata