import ofscraper.models.selector as selector
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.utils.live.progress import (
    activity_counter,
    activity_progress,
    api_job_progress,
    api_overall_progress,
    download_job_progress,
    download_overall_progress,
    like_overall_progress,
    multi_download_job_progress,
    userlist_job_progress,
    userlist_overall_progress,
)
from ofscraper.utils.live.tasks import (
    get_activity_counter_task,
    get_activity_task,
    get_user_first_task,
)


def update_activity_task(**kwargs):
    activity_progress.update(get_activity_task(), **kwargs)


def increment_activity_count(total=None, visible=True, advance=1, **kwargs):
    total = total if total != None else selector.get_num_selected()
    activity_counter.update(
        get_activity_counter_task(),
        advance=advance,
        total=total,
        visible=visible,
        **kwargs
    )


def update_activity_count(visible=True, total=False, **kwargs):
    total = total if total != False else selector.get_num_selected()
    activity_counter.update(
        get_activity_counter_task(), visible=visible, total=total, **kwargs
    )


def increment_user_activity(total=None, visible=True, advance=1, **kwargs):
    total = total if total != None else selector.get_num_selected()
    activity_counter.update(
        get_user_first_task(), total=total, visible=visible, advance=advance, **kwargs
    )


def update_user_activity(visible=True, total=None, **kwargs):
    total = total if total != None else selector.get_num_selected()
    activity_counter.update(
        get_user_first_task(), visible=visible, total=total, **kwargs
    )


def add_api_job_task(*args, **kwargs):
    return api_job_progress.add_task(*args, **kwargs)


def add_api_task(*args, **kwargs):
    return api_overall_progress.add_task(*args, **kwargs)


def remove_api_job_task(task):
    if task == None:
        return
    try:
        api_job_progress.remove_task(task)
    except KeyError:
        pass


def update_api_task(*args, **kwargs):
    return api_overall_progress.update(*args, **kwargs)


def remove_api_job_task(task):
    if task == None:
        return
    try:
        api_job_progress.remove_task(task)
    except KeyError:
        pass


def remove_api_task(task):
    if task == None:
        return
    try:
        api_overall_progress.remove_task(task)
    except KeyError:
        pass


def add_userlist_task(*args, **kwargs):
    return userlist_overall_progress.add_task(*args, **kwargs)


def add_userlist_job_task(*args, **kwargs):
    return userlist_job_progress.add_task(*args, **kwargs)



def update_userlist_task(task,*args, **kwargs):
    if task == None:
        return
    try:
        userlist_overall_progress.update(task,*args,**kwargs)
    except KeyError:
        pass

def remove_userlist_task(task):
    if task == None:
        return
    try:
        userlist_overall_progress.remove_task(task)
    except KeyError:
        pass


def remove_userlist_job_task(task):
    if task == None:
        return
    try:
        userlist_overall_progress.remove_task(task)
    except KeyError:
        pass


downloads_pending = set()


def add_download_job_task(*args, **kwargs):
    max_visible=constants.getattr("MAX_PROGRESS_BARS")
    visible = (
        settings.get_download_bars() and len(download_job_progress.tasks) < max_visible
    )
    task = download_job_progress.add_task(
        *args, visible=visible, start=visible, **kwargs
    )
    if not visible:
        downloads_pending.add(task)
    return task


def add_download_job_multi_task(*args, **kwargs):
    max_visible=constants.getattr("MAX_PROGRESS_BARS")

    visible = (
        settings.get_download_bars() and len(download_job_progress.tasks) < max_visible
    )
    task = multi_download_job_progress.add_task(
        *args, visible=visible, start=visible, **kwargs
    )
    if not visible:
        downloads_pending.add(task)
    return task


def add_download_task(*args, **kwargs):
    return download_overall_progress.add_task(*args, **kwargs)


def start_download_job_task(*args, **kwargs):
    if not settings.get_download_bars():
        return
    download_job_progress.start(*args, **kwargs)


def start_download_multi_job_task(*args, **kwargs):
    if not settings.get_download_bars():
        return
    multi_download_job_progress.start(*args, **kwargs)


def update_download_task(*args, **kwargs):
    return download_overall_progress.update(*args, **kwargs)


def update_download_job_task(*args, **kwargs):
    if not settings.get_download_bars():
        return
    download_job_progress.update(*args, **kwargs)


def update_download_multi_job_task(*args, **kwargs):
    if not settings.get_download_bars():
        return
    multi_download_job_progress.update(*args, **kwargs)


def remove_download_job_task(task):
    min_add_visible = constants.getattr("MIN_ADD_PROGRESS_BARS")

    if task == None:
        return
    try:
        download_job_progress.remove_task(task)
        downloads_pending.discard(task)
        if len(download_job_progress.tasks) < min_add_visible:
            new_task = downloads_pending.pop() if downloads_pending else None
            if not new_task:
                return
            update_download_job_task(new_task, visible=True)
            start_download_job_task(task)
    except KeyError:
        pass


def remove_download_multi_job_task(task):
    min_add_visible = constants.getattr("MIN_ADD_PROGRESS_BARS")

    if task == None:
        return
    try:
        multi_download_job_progress.remove_task(task)
        if len(download_job_progress.tasks) < min_add_visible:
            new_task = downloads_pending.pop() if downloads_pending else None
            if not new_task:
                return
            update_download_multi_job_task(new_task, visible=True)
            start_download_multi_job_task(task)
    except KeyError:
        pass


def remove_download_task(task):
    if task == None:
        return
    try:
        download_overall_progress.remove_task(task)
    except KeyError:
        pass


# like
def add_like_task(*args, **kwargs):
    return like_overall_progress.add_task(*args, **kwargs)
def get_like_task(task):
    return like_overall_progress.tasks[task]
def increment_like_task(*args, advance=1, **kwargs):
    like_overall_progress.update(*args, advance=advance, **kwargs)


def update_like_task(*args, **kwargs):
    like_overall_progress.update(*args, **kwargs)


def remove_like_task(task):
    if task == None:
        return
    try:
        like_overall_progress.remove_task(task)
    except KeyError:
        pass
