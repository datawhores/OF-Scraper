import contextlib
import time

import ofscraper.utils.console as console_
import ofscraper.utils.constants as constants
from ofscraper.utils.live.groups import (
    activity_counter_group,
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
    download_overall_progress_group,
)
from ofscraper.utils.live.live import get_live, stop_live
from ofscraper.utils.live.progress import (
    activity_counter,
    activity_progress,
)
from ofscraper.utils.live.tasks import (
    reset_activity_tasks,
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
def setup_download_progress_live(multi=False, setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        height = max(15, console_.get_shared_console().size[-1] - 2)
        multi_panel.height = height
        single_panel.height = height
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        if multi:
            live = get_live()
            live.update(get_multi_download_progress_group(), refresh=True)
        else:
            live = get_live()
            live.update(get_download_group(), refresh=True)
        yield


@contextlib.contextmanager
def setup_download_overall_progress(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        height = max(15, console_.get_shared_console().size[-1] - 2)
        multi_panel.height = height
        single_panel.height = height
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        live = get_live()
        live.update(download_overall_progress_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_metadata_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_DOWNLOAD_DISPLAY"
        )
        get_live().update(metadata_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_api_split_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_API_DISPLAY"
        )
        get_live().update(api_progress_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_subscription_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
        console_.get_shared_console().quiet = get_quiet_toggle_helper(
            "SUPRESS_SUBSCRIPTION_DISPLAY"
        )
        get_live().update(userlist_group, refresh=True)
        yield


@contextlib.contextmanager
def setup_like_progress_live(setup=False, revert=True, stop=False):
    with live_progress_context(setup=setup, revert=revert, stop=stop):
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
        constants.getattr(key)
        if constants.getattr(key) is not None
        else console_.get_shared_console().quiet
    )
