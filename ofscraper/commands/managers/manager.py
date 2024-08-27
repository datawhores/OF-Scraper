import traceback
import time
import logging


import ofscraper.utils.args.accessors.read as read_args
from ofscraper.__version__ import __version__
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.data.posts.post import post_media_process
import ofscraper.filters.media.main as filters
import ofscraper.utils.args.accessors.areas as areas
import ofscraper.utils.live.tasks as progress_tasks
from ofscraper.commands.utils.strings import (
    area_str,
    avatar_str,
    data_str,
    progress_str,
)


log = logging.getLogger("shared")
import  ofscraper.runner.manager as manager


class commmandManager:
    def __init__(self):
        pass

    def _get_user_action_function(self, funct=None):
        async def wrapper(userdata, session, *args, **kwargs):
            async with session as c:
                data = ["[bold yellow]Normal Mode Results[/bold yellow]"]
                for ele in userdata:
                    username = ele.name
                    model_id = ele.id
                    try:
                        with progress_utils.setup_api_split_progress_live():
                            self._data_helper(ele)
                            all_media, posts, like_posts = await post_media_process(
                                ele, c=c
                            )

                            text_posts = filters.filterPostFinalText(posts)
                            like_posts = filters.post_filter_for_like(like_posts)

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
                            result = await funct(
                                media=all_media,
                                posts=text_posts,
                                like_posts=like_posts,
                                ele=ele,
                            )
                            data.extend(result)
                    except Exception as e:

                        log.traceback_(f"failed with exception: {e}")
                        log.traceback_(traceback.format_exc())

                        if isinstance(e, KeyboardInterrupt):
                            raise e
                    finally:
                        progress_updater.increment_user_activity()
                progress_updater.update_activity_task(
                    description="Finished Action Mode"
                )
                time.sleep(1)
                return data

        return wrapper

    def _get_userfirst_data_function(self, funct):
        async def wrapper(userdata, session, *args, **kwargs):
            progress_updater.update_activity_task(
                description="Getting all user data first"
            )
            progress_updater.update_user_activity(
                description="Users with Data Retrieved"
            )
            progress_updater.update_activity_count(
                description="Overall progress", total=2
            )
            data = {}
            async with session as c:
                for ele in userdata:
                    try:
                        self._data_helper(ele)
                        with progress_utils.setup_activity_counter_live(revert=False):
                            data.update(await funct(c, ele))
                    except Exception as e:
                        log.traceback_(f"failed with exception: {e}")
                        log.traceback_(traceback.format_exc())
                        if isinstance(e, KeyboardInterrupt):
                            raise e
                    finally:
                        c.reset_sleep()
                        progress_updater.increment_user_activity()
            return data

        return wrapper

    def _get_userfirst_action_execution_function(self, funct):
        async def wrapper(data, *args, **kwargs):
            out = ["[bold yellow]User First Results[/bold yellow]"]
            progress_updater.increment_activity_count(total=2)
            try:
                progress_updater.update_user_activity(total=len(data.items()))
                for _, val in data.items():
                    all_media = val["media"]
                    posts = val["posts"]
                    like_posts = val["like_posts"]
                    ele = val["ele"]
                    avatar = ele.avatar
                    if (
                        constants.getattr("SHOW_AVATAR")
                        and avatar
                        and read_args.retriveArgs().userfirst
                    ):
                        logging.getLogger("shared_other").warning(
                            avatar_str.format(avatar=avatar)
                        )
                    try:
                        with progress_utils.setup_activity_counter_live(revert=False):
                            result = await funct(
                                posts,
                                like_posts,
                                *args,
                                media=all_media,
                                ele=ele,
                                **kwargs,
                            )
                            out.extend(result)
                    except Exception as e:
                        log.traceback_(f"failed with exception: {e}")
                        log.traceback_(traceback.format_exc())
                        if isinstance(e, KeyboardInterrupt):
                            raise e
                    finally:
                        progress_updater.increment_user_activity()
            except Exception as e:
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())
                if isinstance(e, KeyboardInterrupt):
                    raise e
            finally:
                progress_updater.increment_activity_count(
                    description="Overall progress", total=2
                )
            return out

        return wrapper

    def _data_helper(self, user):
        avatar = user.avatar
        username = user.name
        active = user.active
        final_post_areas = areas.get_final_posts_area()
        length =manager.Manager.model_manager.get_num_selected()
        count = progress_tasks.get_user_task_obj().completed
        logging.getLogger("shared_other").warning(
            progress_str.format(count=count + 1, length=length)
        )
        logging.getLogger("shared_other").warning(data_str.format(name=username))
        if constants.getattr("SHOW_AVATAR") and avatar:
            logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
        progress_updater.update_activity_task(
            description=area_str.format(
                areas=",".join(final_post_areas), name=username, active=active
            )
        )
        logging.getLogger("shared_other").info(
            area_str.format(
                areas=",".join(final_post_areas), name=username, active=active
            )
        )

    @property
    def run_action(self):
        return len(read_args.retriveArgs().action) > 0
