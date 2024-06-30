import logging

import ofscraper.db.operations as operations
import ofscraper.utils.context.exit as exit
import ofscraper.utils.live.updater as progress_updater
from ofscraper.commands.scraper.execute import execute_user_action
from ofscraper.commands.utils.post import post_media_process
from ofscraper.commands.utils.wrappers.user_first import (
    get_userfirst_action_execution_function,
    get_userfirst_data_function,
)
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@exit.exit_wrapper
@run
async def process_users_actions_user_first(userdata, session):
    data = await get_userfirst_data_function(get_users_data_user_first)(
        userdata, session
    )
    progress_updater.update_activity_task(description="Performing Actions on Users")
    progress_updater.update_user_activity(
        description="Users with Actions completed", completed=0
    )

    return await get_userfirst_action_execution_function(execute_user_action)(data)


async def get_users_data_user_first(session, ele):
    return await process_ele_user_first_data_retriver(ele, session)


async def process_ele_user_first_data_retriver(ele, session):
    model_id = ele.id
    username = ele.name
    avatar = ele.avatar
    await operations.table_init_create(model_id=model_id, username=username)
    media, posts, like_posts = await post_media_process(ele, session)
    return {
        model_id: {
            "username": username,
            "posts": posts,
            "media": media,
            "avatar": avatar,
            "like_posts": like_posts,
            "ele": ele,
        }
    }
