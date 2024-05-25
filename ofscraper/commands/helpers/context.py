import contextlib
import logging
import traceback

import ofscraper.models.selector as selector
import ofscraper.utils.args.helpers.areas as areas
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.scraper.post import post_media_process

from ofscraper.commands.helpers.strings import (
    area_str,
    avatar_str,
    data_str,
    progress_str,
)
log = logging.getLogger("shared")


def get_user_action_function(func):
    async def wrapper(userdata,session,*args, **kwargs):
        async with session as c:
            for ele in userdata:
                try:
                    progress_utils.switch_api_progress() 
                    all_media, posts, like_posts = await post_media_process(ele, c=c)
                    avatar = ele.avatar
                    if (
                        constants.getattr("SHOW_AVATAR")
                        and avatar
                        and read_args.retriveArgs().userfirst
                    ):
                        logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
                    await func(all_media, posts, like_posts)
                    ele = kwargs.get("ele") or kwargs.get("user")
                    data_helper(ele)
                    await func(*args, **kwargs)
                except Exception as e:

                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())

                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_utils.increment_user_activity()
            



    return wrapper




def get_userfirst_data_function(funct):
    async def wrapper(userdata, session, *args, **kwargs):
        progress_utils.update_activity_task(description="Getting all user data first")
        progress_utils.update_user_activity(description="Users with Data Retrieved")
        progress_utils.update_activity_count(description="Overall progress", total=2)
        data = {}
        async with session:
            for ele in userdata:
                try:
                    with user_first_data_inner_context(session, ele):
                        data.update(await funct(session, ele))
                except Exception as e:
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_utils.increment_user_activity()
        return data

    return wrapper


def get_userfirst_action_execution_function(funct):
    async def wrapper(data,*args, **kwargs):
        progress_utils.increment_activity_count(total=2)
        try:
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
                    logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
                try:
                    while progress_utils.setup_activity_live():
                        await funct(all_media, posts, like_posts,*args, ele=ele,**kwargs)
                except Exception as e:
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_utils.increment_user_activity()
        except Exception as e:
            log.traceback_(f"failed with exception: {e}")
            log.traceback_(traceback.format_exc())
            if isinstance(e, KeyboardInterrupt):
                raise e
        finally:
            progress_utils.increment_activity_count(description="Overall progress", total=2)

    return wrapper


@contextlib.contextmanager
def normal_data_context(session, user):
    data_helper(user)
    yield
    session.reset_sleep()


@contextlib.contextmanager
def user_first_data_inner_context(session, user):
    data_helper(user)
    yield
    session.reset_sleep()
    progress_utils.increment_user_activity()


def data_helper(user):
    avatar = user.avatar
    username = user.name
    active = user.active
    final_post_areas = areas.get_final_posts_area()
    length = selector.get_num_selected()
    count = progress_utils.get_user_task_obj().completed


    logging.getLogger("shared_other").warning(
        progress_str.format(count=count + 1, length=length)
    )
    logging.getLogger("shared_other").warning(data_str.format(name=username))
    if constants.getattr("SHOW_AVATAR") and avatar:
        logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
    progress_utils.update_activity_task(
        description=area_str.format(
            areas=",".join(final_post_areas), name=username, active=active
        )
    )
    logging.getLogger("shared_other").info(
        area_str.format(areas=",".join(final_post_areas), name=username, active=active)
    )
