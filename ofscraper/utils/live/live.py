import contextlib


import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants

from ofscraper.utils.live.progress import download_job_progress,download_overall_progress,multi_download_job_progress,live,activity_counter,activity_progress,userlist_overall_progress,api_job_progress,api_overall_progress

from ofscraper.utils.live.groups import api_progress_group,multi_panel,single_panel,like_progress_group,get_download_group,get_multi_download_progress_group,userlist_group,activity_group
from ofscraper.utils.live.tasks import activity_counter_task,activity_task,user_first_task

from ofscraper.utils.live.getter import get_user_task
from ofscraper.utils.live.updater import update_activity_task,increment_activity_count,update_activity_count,add_api_job_task,remove_api_job_task,add_userlist_task,remove_userlist_task,remove_userlist_job_task,add_userlist_job_task,add_api_task,update_api_task,remove_api_task,update_activity_task,add_download_task,add_download_job_task,add_download_job_multi_task,update_download_job_task,remove_download_job_task,remove_download_task,remove_download_multi_job_task,update_download_multi_job_task,increment_user_activity,update_user_activity,add_like_task,increment_like_task,remove_like_task,update_download_task
#main context and switches
@contextlib.contextmanager
def live_progress_context(stop=False,revert=True):
    if not live.is_started:
        live.start()
    old_render=live.renderable
    yield
    if revert and old_render:
        live.update(old_render)
    if stop:
        remove_task()
        live.stop()
def remove_task():
    if activity_task:
        activity_progress.remove_task(
            activity_task
     )
    if user_first_task:
        activity_counter.remove_task(
            user_first_task
     )
    if activity_counter_task:
            activity_counter.remove_task(
            activity_counter_task
     )


@contextlib.contextmanager
def setup_download_progress_live(multi=False,stop=False):
    with live_progress_context(stop=stop):
        height=max(15, console_.get_shared_console().size[-1] - 2)
        multi_panel.height=height
        single_panel.height=height
        console_.get_shared_console().quiet=get_quiet_toggle_helper("SUPRESS_DOWNLOAD_DISPLAY")
        if multi:
            live.update(get_multi_download_progress_group(),refresh=True)
        else:
            live.update(get_download_group(),refresh=True)
        yield
@contextlib.contextmanager

def setup_api_split_progress_live(stop=False):
    with live_progress_context(stop=stop):
        console_.get_shared_console().quiet=get_quiet_toggle_helper("SUPRESS_API_DISPLAY")
        live.update(api_progress_group,refresh=True)
        yield


@contextlib.contextmanager
def setup_subscription_progress_live(stop=False):
    with live_progress_context(stop=stop):
        console_.get_shared_console().quiet=get_quiet_toggle_helper("SUPRESS_SUBSCRIPTION_DISPLAY")
        live.update(userlist_group,refresh=True)
        yield


@contextlib.contextmanager
def setup_like_progress_live(stop=False):
    with live_progress_context(stop=stop):
        console_.get_shared_console().quiet=get_quiet_toggle_helper("SUPRESS_LIKE_DISPLAY")
        live.update(like_progress_group,refresh=True)
        yield

def switch_api_progress():
    global api_progress_group
    global live
    if not api_progress_group:
        return
    console_.get_shared_console().quiet=get_quiet_toggle_helper("SUPRESS_API_DISPLAY")
    live.update(api_progress_group,refresh=True)

@contextlib.contextmanager
def setup_all_paid_database_live(stop=False):
    with live_progress_context(stop=stop):
        console_.get_shared_console().quiet=get_quiet_toggle_helper("SUPRESS_API_DISPLAY")
        live.update(activity_group,refresh=True)
        yield

def get_quiet_toggle_helper(key):
    return constants.getattr(key) if constants.getattr(key)!=None else console_.get_shared_console().quiet