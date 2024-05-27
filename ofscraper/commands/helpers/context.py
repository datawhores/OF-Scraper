import logging
import traceback


import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.scraper.post import post_media_process

from ofscraper.commands.helpers.strings import (
    avatar_str,
)
log = logging.getLogger("shared")


def get_user_action_function(func):
    async def wrapper(userdata,session,*args, **kwargs):
        async with session as c:
            data=["[bold yellow]User First Progress[/bold yellow]"]
            for ele in userdata:
                try:
                    with progress_utils.setup_api_split_progress_live():
                        data_helper(ele)
                        all_media, posts, like_posts = await post_media_process(ele, c=c)
                    with progress_utils.setup_activity_group_live(revert=False):
                        avatar = ele.avatar
                        if (
                            constants.getattr("SHOW_AVATAR")
                            and avatar
                            and read_args.retriveArgs ().userfirst
                        ):
                            logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
                        data.append(await func(all_media, posts, like_posts,ele=ele))
                except Exception as e:

                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())

                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_utils.increment_user_activity()
            return data
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
                    data_helper(ele)
                    with progress_utils.setup_activity_counter_live(revert=False):
                        data.update(await funct(session, ele))
                except Exception as e:
                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())
                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    session.reset_sleep()
                    progress_utils.increment_user_activity()
        return data

    return wrapper


def get_userfirst_action_execution_function(funct):
    async def wrapper(data,*args, **kwargs):
        progress_utils.increment_activity_count(total=2)
        try:
             progress_utils.update_user_activity(total=len(data.items()))
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
                    with progress_utils.setup_activity_counter_live(revert=False):
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




