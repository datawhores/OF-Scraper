import asyncio
from ofscraper.utils.live.progress import download_job_progress,download_overall_progress,multi_download_job_progress,activity_counter,activity_progress,api_job_progress,userlist_overall_progress,userlist_job_progress,api_overall_progress


from ofscraper.utils.live.tasks import activity_counter_task,activity_task,user_first_task
import ofscraper.utils.settings as settings

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

def add_api_job_task(*args,**kwargs):
    return api_job_progress.add_task(*args,**kwargs)


def add_api_task(*args,**kwargs):
    return api_overall_progress.add_task(*args,**kwargs)
def remove_api_job_task(task):
    if task==None:
        return
    try:
        api_job_progress.remove_task(task)
    except KeyError:
        pass

def update_api_task(*args,**kwargs):
    return api_overall_progress.update(*args,**kwargs)


def remove_api_job_task(task):
    if task==None:
        return
    try:
        api_job_progress.remove_task(task)
    except KeyError:
        pass

def remove_api_task(task):
    if task==None:
        return
    try:
        api_overall_progress.remove_task(task)
    except KeyError:
        pass
def add_userlist_task(*args,**kwargs):
   return userlist_overall_progress.add_task(*args,**kwargs)


def add_userlist_job_task(*args,**kwargs):
   return userlist_job_progress.add_task(*args,**kwargs)

def remove_userlist_task(task):
    if task==None:
        return
    try:
        userlist_overall_progress.remove_task(task)
    except KeyError:
        pass

def remove_userlist_job_task(task):
    if task==None:
        return
    try:
        userlist_overall_progress.remove_task(task)
    except KeyError:
        pass


def add_download_job_task(*args,**kwargs):
   return download_job_progress.add_task(*args,**kwargs)

def add_download_job_multi_task(*args,**kwargs):
   return multi_download_job_progress.add_task(*args,**kwargs)

def add_download_task(*args,**kwargs):
   return download_overall_progress.add_task(*args,**kwargs)

def update_download_job_task(*args,**kwargs):
    if not settings.get_download_bars():
        return
    download_job_progress.update(*args,**kwargs)

def update_download_multi_job_task(*args,**kwargs):
    if not settings.get_download_bars():
        return
    multi_download_job_progress.update(*args,**kwargs)
def remove_download_job_task(task):
    if task==None:
        return
    try:
        download_job_progress.remove_task(task)
    except KeyError:
        pass

def remove_download_multi_job_task(task):
    if task==None:
        return
    try:
        multi_download_job_progress.remove_task(task)
    except KeyError:
        pass
def remove_download_task(task):
    if task==None:
        return
    try:
        download_overall_progress.remove_task(task)
    except KeyError:
        pass