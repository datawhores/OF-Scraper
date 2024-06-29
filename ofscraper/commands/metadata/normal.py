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

import ofscraper.utils.live.updater as progress_updater
from ofscraper.commands.metadata.execute import execute_metadata_action_on_user
from ofscraper.commands.utils.wrappers.normal import get_user_action_function_meta
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")


@run
# entrypoint for normal run
async def process_users_metadata_normal(userdata, session):
    user_action_funct = get_user_action_function_meta(execute_metadata_action_on_user)
    progress_updater.update_user_activity(description="Users with Updated Metadata")
    return await user_action_funct(userdata, session)
