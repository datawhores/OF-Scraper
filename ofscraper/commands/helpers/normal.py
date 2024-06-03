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


def get_user_action_function(func):
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







