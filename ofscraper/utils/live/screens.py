import contextlib
import time

import ofscraper.utils.console as console_
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.live.groups import (
    activity_counter_group,
    activity_group,
    activity_progress_group,
    api_progress_group,
    get_download_group,
    like_progress_group,
    metadata_group,
    single_panel,
    userlist_group,
)
from ofscraper.utils.live.live import get_live, stop_live
from ofscraper.utils.live.progress import (
    activity_counter,
    activity_progress,
)
from ofscraper.utils.live.tasks import (
    reset_activity_tasks,
)

from ofscraper.utils.live.updater import (
    clear_api_tasks,
    clear_download_tasks,
    clear_like_tasks,
    clear_metadata_tasks,
    clear_userlist_tasks,
    clear_all_tasks
)


# main context and switches
@contextlib.contextmanager
def live_progress_context(setup=False, revert=True, stop=False):
    old_render = get_live().renderable
    if setup:
        remove_task()
    if not get_live().is_started:
        get_live().start()
    yield
    if stop:
        stop_live()
        console_.get_console().clear_live()
        ##give time for console to clear
        time.sleep(0.3)
    elif revert and old_render:
        get_live().update(old_render)


def remove_task():
    for task in activity_progress.task_ids:
        activity_progress.remove_task(task)
    for task in activity_counter.task_ids:
        activity_counter.remove_task(task)
    reset_activity_tasks()


@contextlib.contextmanager
def setup_download_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        height = max(15, console_.get_shared_console().size[-1] - 2)
        single_panel.height = height
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        live = get_live()
        live.update(get_download_group(), refresh=True)
        yield
        clear_download_tasks()



@contextlib.contextmanager
def setup_metadata_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        get_live().update(metadata_group, refresh=True)
        yield
        clear_metadata_tasks()


@contextlib.contextmanager
def setup_api_split_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(api_progress_group, refresh=True)
        yield
        clear_api_tasks()


@contextlib.contextmanager
def setup_subscription_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_SUBSCRIPTION_DISPLAY"
        )
        get_live().update(userlist_group, refresh=True)
        yield
        clear_userlist_tasks()


@contextlib.contextmanager
def setup_like_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_LIKE_DISPLAY"
        )
        get_live().update(like_progress_group, refresh=True)
        yield
        clear_like_tasks()


def switch_api_progress():
    global api_progress_group
    global live
    if not api_progress_group:
        return
    console_.get_shared_console().quiet = get_quiet_toggle_helper("SUPRESS_API_DISPLAY")
    get_live().update(api_progress_group, refresh=True)


@contextlib.contextmanager
def setup_activity_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_progress_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_all_paid_database_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_activity_group_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_group, refresh=True)
        yield
        clear_all_tasks()


@contextlib.contextmanager
def setup_activity_counter_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(activity_counter_group, refresh=True)
        yield


def get_quiet_toggle_helper(key):
    return (
        of_env.getattr(key)
        if of_env.getattr(key) is not None
        else console_.get_shared_console().quiet
    )
