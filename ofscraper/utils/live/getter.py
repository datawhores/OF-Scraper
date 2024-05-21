from ofscraper.utils.live.progress import activity_counter

from ofscraper.utils.live.tasks import user_first_task
def get_user_task():
    try:
        return activity_counter.tasks[user_first_task]
    except:
        pass