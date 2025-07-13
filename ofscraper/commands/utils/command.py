import traceback
import logging


import ofscraper.utils.of_env.of_env as of_env
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
import ofscraper.managers.manager as manager
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


class CommandManager:
    def __init__(self):
        pass

    async def _process_users_normal(self, userdata: list, session, action_func):
        """
        Processes users one by one, fetching data and then executing an action.
        """
        async with session as c:
            for ele in userdata:
                try:
                    # reset user activity to initiial
                    self._data_helper(ele)
                    postcollection = await post_media_process(ele, c=c)
                    self._avatar_helper(ele)
                    # show progress bars/set string in action function
                    await action_func(ele=ele, postcollection=postcollection)
                except Exception as e:
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_updater.activity.update_user(advance=1, visible=True)

    async def _gather_user_first_data(self, userdata: list, session, data_func):
        """
        Phase 1 of user-first mode: Gathers all data for all users.
        """
        progress_updater.activity.update_user(
            description="Users with Data Retrieved", total=len(userdata), visible=True
        )
        all_data = {}
        progress_updater.activity.update_overall(
            completed=0, visible=True, total=2, description="Overall Progress"
        )
        async with session as c:
            for ele in userdata:
                try:
                    self._data_helper(ele)
                    all_data.update(await data_func(c, ele))
                except Exception as e:
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    c.reset_sleep()
                    progress_updater.activity.update_user(advance=1, visible=True)
        progress_updater.activity.update_overall(advance=1, visible=True)
        return all_data

    async def _execute_user_first_actions(self, userdata: dict, action_func):
        """
        Phase 2 of user-first mode: Executes actions on the gathered data.
        """
        progress_updater.activity.update_user(
            description="Users with Action Completed",
            total=len(userdata),
            visible=True,
            completed=0,
        )

        for _, val in userdata.items():
            try:
                self._avatar_helper(val["ele"])
                await action_func(
                    postcollection=val["postcollection"],
                    ele=val["ele"],
                )
            except Exception as e:
                log.traceback_(f"failed with exception: {e}")
                log.traceback_(traceback.format_exc())
                if isinstance(e, KeyboardInterrupt):
                    raise e
            finally:
                progress_updater.activity.update_user(advance=1, visible=True)
        progress_updater.activity.update_overall(advance=1, visible=True)

    def _data_helper(self, user):
        avatar = user.avatar
        username = user.name
        active = user.active
        final_post_areas = areas.get_final_posts_area()
        length = manager.Manager.model_manager.get_num_all_selected_models()
        count = progress_tasks.get_user_task_obj().completed
        logging.getLogger("shared").warning(
            progress_str.format(count=count + 1, length=length)
        )
        logging.getLogger("shared").warning(data_str.format(name=username))
        if of_env.getattr("SHOW_AVATAR") and avatar:
            logging.getLogger("shared").warning(avatar_str.format(avatar=avatar))
        progress_updater.activity.update_task(
            description=area_str.format(
                areas=",".join(final_post_areas), name=username, active=active
            ),
            visible=True,
        )
        logging.getLogger("shared").info(
            area_str.format(
                areas=",".join(final_post_areas), name=username, active=active
            )
        )

    def _avatar_helper(self, ele):
        avatar = ele.avatar
        if (
            of_env.getattr("SHOW_AVATAR")
            and avatar
            and settings.get_settings().userfirst
        ):
            logging.getLogger("shared").warning(avatar_str.format(avatar=avatar))

    @property
    def run_action(self):
        return len(settings.get_settings().actions) > 0
