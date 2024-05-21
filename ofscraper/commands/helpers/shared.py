import logging
import ofscraper.utils.live.live as progress_utils
import ofscraper.utils.constants as constants
from ofscraper.commands.helpers.strings import avatar_str

def user_first_data_preparer():
    progress_utils.update_activity_task(description="Getting all user Data First")
    progress_utils.update_user_first_activity(description="Users with Data Retrived")
    progress_utils.update_activity_count(description="Overall progress",total=2)



   