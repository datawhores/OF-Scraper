from ofscraper.utils.live.progress import activity_counter, activity_progress

activity_task = None
activity_counter_task = None
user_first_task = None


def get_activity_task():
    global activity_task
    if activity_task is None:
        activity_task = activity_progress.add_task(description="Running OF-Scraper")
    return activity_task


def get_activity_counter_task():
    global activity_counter_task
    if activity_counter_task is None:
        activity_counter_task = activity_counter.add_task(
            description="Overall script progress", visible=False, total=None
        )
    return activity_counter_task


def get_user_first_task():
    global user_first_task
    if user_first_task is None:
        user_first_task = activity_counter.add_task(
            description="", visible=False, total=None
        )
    return user_first_task


def reset_activity_tasks():
    global activity_task
    global activity_counter_task
    global user_first_task
    activity_task = None
    activity_counter_task = None
    user_first_task = None


def get_user_task_obj():
    try:
        task = get_user_first_task()
        return activity_counter._tasks[task]
    except:
        pass
