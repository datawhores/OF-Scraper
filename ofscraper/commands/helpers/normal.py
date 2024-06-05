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
from ofscraper.commands.helpers.data import data_helper
import ofscraper.filters.media.main as filters



def get_user_action_function(func):
    async def wrapper(userdata,session,*args, **kwargs):
        async with session as c:
            data=["[bold yellow]Normal Mode Results[/bold yellow]"]
            for ele in userdata:
                username=ele.name
                model_id=ele.id
                try:
                    with progress_utils.setup_api_split_progress_live():
                        data_helper(ele)
                        all_media, posts, like_posts = await post_media_process(ele, c=c)
                        all_media=filters.filtermediaFinal(all_media, model_id=model_id, username=username)
                        posts=  filters.filterPostFinal(posts)
                        like_posts=filters.post_filter_for_like(like_posts)

                    with progress_utils.setup_activity_group_live(revert=False):
                        avatar = ele.avatar
                        if (
                            constants.getattr("SHOW_AVATAR")
                            and avatar
                            and read_args.retriveArgs ().userfirst
                        ):
                            logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
                        data.extend(await func(media=all_media, posts=posts, like_posts=like_posts,ele=ele))
                except Exception as e:

                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())

                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_utils.increment_user_activity()
            return data
    return wrapper




def get_user_action_function_meta(func):
    async def wrapper(userdata,session,*args, **kwargs):
        async with session as c:
            data=["[bold yellow]Normal Mode Results[/bold yellow]"]
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
                        data.extend(await func(media=all_media, posts=posts, like_posts=like_posts,ele=ele))
                except Exception as e:

                    log.traceback_(f"failed with exception: {e}")
                    log.traceback_(traceback.format_exc())

                    if isinstance(e, KeyboardInterrupt):
                        raise e
                finally:
                    progress_utils.increment_user_activity()
            return data
    return wrapper




