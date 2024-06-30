r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      
"""

import logging
import traceback

import ofscraper.db.operations as operations
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.screens as progress_updater
from ofscraper.commands.metadata.execute import execute_metadata_action_on_user
from ofscraper.commands.utils.post import process_areas
from ofscraper.commands.utils.wrappers.user_first import (
    get_userfirst_action_execution_function,
    get_userfirst_data_function,
)
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


# entrypoint for userfirst
@run
async def metadata_user_first(userdata, session):
    data = await get_userfirst_data_function(metadata_data_user_first)(
        userdata, session
    )
    progress_updater.update_activity_task(description="Changing Metadata for Users")
    progress_updater.update_user_activity(
        description="Users with Metadata Changed", completed=0
    )
    # pass all data to userfirst
    return await get_userfirst_action_execution_function(
        execute_metadata_action_on_user
    )(data)


# data functions
@run
async def metadata_data_user_first(session, ele):
    try:
        return await process_ele_user_first_data_retriver(ele=ele, session=session)
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())


async def process_ele_user_first_data_retriver(ele=None, session=None):
    data = {}
    progress_utils.switch_api_progress()
    model_id = ele.id
    username = ele.name
    avatar = ele.avatar
    try:
        model_id = ele.id
        username = ele.name
        await operations.table_init_create(model_id=model_id, username=username)
        media, _, _ = await process_areas(ele, model_id, username, c=session)
        return {
            model_id: {
                "username": username,
                "media": media,
                "avatar": avatar,
                "ele": ele,
                "posts": [],
                "like_posts": [],
            }
        }
    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            raise e
        log.traceback_(f"failed with exception: {e}")
        log.traceback_(traceback.format_exc())
    return data
