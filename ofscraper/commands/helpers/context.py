import logging
import contextlib

import ofscraper.utils.constants as constants
import ofscraper.utils.live.live as progress_utils
from ofscraper.commands.helpers.strings import avatar_str,area_str,progress_str,data_str
import ofscraper.utils.args.areas as areas

@contextlib.contextmanager
def user_first_data_inner_context(session,length,count,user):
    avatar=user.avatar
    username=user.name
    active=user.active
    final_post_areas=areas.get_final_posts_area()
    progress_utils.switch_api_progress()
    logging.getLogger("shared_other").warning(progress_str.format(count=count+1,length=length))
    logging.getLogger("shared_other").warning(data_str.format(name=username))
    if constants.getattr("SHOW_AVATAR") and avatar:
        logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
    progress_utils.update_activity_task(description=area_str.format(areas=",".join(final_post_areas),name=username,active=active))
    logging.getLogger("shared_other").info(
            area_str.format(areas=",".join(final_post_areas),name=username,active=active)
            )
    yield
    session.reset_sleep()
    progress_utils.increment_user_first_activity()
@contextlib.contextmanager
def user_first_action_runner_inner_context(avatar):
    if constants.getattr("SHOW_AVATAR") and avatar:
        logging.getLogger("shared_other").warning(avatar_str.format(avatar=avatar))
    yield 
    progress_utils.increment_user_first_activity()
@contextlib.contextmanager
def user_first_action_runner_outer_context():
    progress_utils.increment_activity_count(total=2)
    yield 
    progress_utils.increment_activity_count(description="Overall progress",total=2)