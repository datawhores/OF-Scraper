import asyncio
from ofscraper.utils.live.progress import download_job_progress,download_overall_progress,multi_download_job_progress,live,activity_counter,activity_progress,api_job_progress,userlist_overall_progress,userlist_job_progress,api_overall_progress


from ofscraper.utils.live.tasks import activity_counter_task,activity_task,user_first_task
def update_activity_task(**kwargs):
    activity_progress.update(
           activity_task, **kwargs
    )

def increment_activity_count():
    activity_counter.update(
           activity_counter_task,advance=1
    )


def update_activity_count(**kwargs):
    activity_counter.update(
           activity_counter_task,**kwargs
    )



def add_user_first_activity(**kwargs):
    activity_counter.update(
            user_first_task,**kwargs
    )

def increment_user_first_activity():
    activity_counter.update(
           user_first_task,advance=1
    )

def update_first_activity(**kwargs):
    activity_counter.update(
          user_first_task,  **kwargs
    )

#API
lock=asyncio.Lock()

def add_apijob_task(*args,**kwargs):
    return api_job_progress.add_task(*args,**kwargs)


def add_api_task(*args,**kwargs):
    return api_overall_progress.add_task(*args,**kwargs)
def remove_apijob_task(task):
    if not task:
        return
    try:
        api_job_progress.remove_task(task)
    except KeyError:
        pass

def update_api_task(*args,**kwargs):
    return api_overall_progress.update(*args,**kwargs)


def remove_apijob_task(task):
    if not task:
        return
    try:
        api_job_progress.remove_task(task)
    except KeyError:
        pass

def remove_api_task(task):
    if not task:
        return
    try:
        api_overall_progress.remove_task(task)
    except KeyError:
        pass
def add_userlist_task(*args,**kwargs):
   return userlist_overall_progress.add_task(*args,**kwargs)


def add_userlistjob_task(*args,**kwargs):
   return userlist_job_progress.add_task(*args,**kwargs)

def remove_userlist_task(task):
    if not task:
        return
    try:
        userlist_overall_progress.remove_task(task)
    except KeyError:
        pass

def remove_userlistjob_task(task):
    if not task:
        return
    try:
        userlist_overall_progress.remove_task(task)
    except KeyError:
        pass

