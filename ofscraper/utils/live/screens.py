import contextlib

import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
from ofscraper.utils.live.groups import (
    activity_group,
    activity_progress_group,
    api_progress_group,
    get_download_group,
    get_multi_download_progress_group,
    like_progress_group,
    metadata_group,
    multi_panel,
    single_panel,
    userlist_group,
    activity_counter_group
)
from ofscraper.utils.live.live import get_live, set_live
from ofscraper.utils.live.progress import (
    activity_counter,
    activity_progress,
    api_job_progress,
    api_overall_progress,
    download_job_progress,
    download_overall_progress,
    multi_download_job_progress,
    userlist_overall_progress,
)
from ofscraper.utils.live.tasks import (
    activity_counter_task,
    activity_task,
    get_user_task_obj,
    reset_activity_tasks,
    user_first_task,
)
from ofscraper.utils.live.updater import (
    add_api_job_task,
    update_userlist_task,
    add_api_task,
    add_download_job_multi_task,
    add_download_job_task,
    add_download_task,
    add_like_task,
    add_userlist_job_task,
    add_userlist_task,
    increment_activity_count,
    increment_like_task,
    increment_user_activity,
    remove_api_job_task,
    remove_api_task,
    remove_download_job_task,
    remove_download_multi_job_task,
    remove_download_task,
    remove_like_task,
    remove_userlist_job_task,
    remove_userlist_task,
    update_activity_count,
    update_activity_task,
    update_api_task,
    update_download_job_task,
    update_download_multi_job_task,
    update_download_task,
    update_user_activity,
    get_like_task
)


# main context and switches
@contextlib.contextmanager
def live_progress_context(setup=False,revert=True):
    old_render = get_live().renderable
    if setup:
        remove_task()
    if not get_live().is_started:
        get_live().start()
    yield
    if revert and old_render:
        get_live().update(old_render)

def remove_task():
    for task in activity_progress.task_ids:
        activity_progress.remove_task(task)
    for task in activity_counter.task_ids:
        activity_counter.remove_task(task)
    reset_activity_tasks()


@contextlib.contextmanager
def setup_download_progress_live(multi=False, setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        height = max(15, console_.get_shared_console().size[-1] - 2)
        multi_panel.height = height
        single_panel.height = height
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        if multi:
            get_live().update(get_multi_download_progress_group(), refresh=True)
        else:
            get_live().update(get_download_group(), refresh=True)
        yield


@contextlib.contextmanager
def setup_metadata_progress_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        get_live().update(metadata_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_api_split_progress_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(api_progress_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_subscription_progress_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_SUBSCRIPTION_DISPLAY"
        )
        get_live().update(userlist_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_like_progress_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_LIKE_DISPLAY"
        )
        get_live().update(like_progress_group, refresh=True)
        yield


def switch_api_progress():
    global api_progress_group
    global live
    if not api_progress_group:
        return
    console_.get_shared_console().quiet = get_quiet_toggle_helper("SUPRESS_API_DISPLAY")
    get_live().update(api_progress_group, refresh=True)


@contextlib.contextmanager
def setup_activity_progress_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_progress_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_all_paid_database_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_activity_group_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_activity_counter_live(setup=False,revert=True):
    with live_progress_context(setup=setup,revert=revert):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_counter_group, refresh=True)
        yield

def get_quiet_toggle_helper(key):
    return (
        constants.getattr(key)
        if constants.getattr(key) != None
        else console_.get_shared_console().quiet
    )
