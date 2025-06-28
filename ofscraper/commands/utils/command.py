import traceback
import time
import logging


import ofscraper.utils.of_env.of_env as of_env
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
import ofscraper.main.manager as manager
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


class commmandManager:
    def __init__(self):
        pass

    def _get_user_action_function(self, funct=None):
        async def wrapper(userdata, session, *args, **kwargs):
            async with session as c:
                data = ["[bold yellow]Normal Mode Results[/bold yellow]"]
                for ele in userdata:
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
                            result = await funct(
                                media=postcollection.get_media_to_download(),
                                posts=postcollection.get_posts_for_text_download(),
                                like_posts=postcollection.get_posts_to_like(),
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
                        of_env.getattr("SHOW_AVATAR")
                        and avatar
                        and settings.get_settings().userfirst
                    ):
                        logging.getLogger("shared").warning(
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
        length = manager.Manager.model_manager.num_models_selected
        count = progress_tasks.get_user_task_obj().completed
        logging.getLogger("shared").warning(
            progress_str.format(count=count + 1, length=length)
        )
        logging.getLogger("shared").warning(data_str.format(name=username))
        if of_env.getattr("SHOW_AVATAR") and avatar:
            logging.getLogger("shared").warning(avatar_str.format(avatar=avatar))
        progress_updater.update_activity_task(
            description=area_str.format(
                areas=",".join(final_post_areas), name=username, active=active
            )
        )
        logging.getLogger("shared").info(
            area_str.format(
                areas=",".join(final_post_areas), name=username, active=active
            )
        )

    @property
    def run_action(self):
        return len(settings.get_settings().action) > 0
