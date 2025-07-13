import ofscraper.utils.console as console
from typing import List, Union
from ofscraper.utils.live.progress import (
    activity_counter,
    activity_desc,
    api_job_progress,
    api_overall_progress,
    download_job_progress,
    download_overall_progress,
    metadata_overall_progress,
    like_overall_progress,
    userlist_job_progress,
    userlist_overall_progress,
)


def clear():
    console.get_shared_console().clear_live()
    console.get_shared_console().line(2)


def _hide_tasks_in_progress(progress_instance):
    """Helper function to hide all tasks in a given Progress instance."""
    try:
        for task in progress_instance.tasks:
            progress_instance.update(task.id, visible=False)
    except Exception:
        pass  # Failsafe for any potential race conditions or errors


def clear_api_tasks():
    _hide_tasks_in_progress(api_job_progress)
    _hide_tasks_in_progress(api_overall_progress)


def clear_download_tasks():
    _hide_tasks_in_progress(download_job_progress)
    _hide_tasks_in_progress(download_overall_progress)


def clear_metadata_tasks():
    _hide_tasks_in_progress(metadata_overall_progress)


def clear_like_tasks():
    _hide_tasks_in_progress(like_overall_progress)


def clear_userlist_tasks():
    _hide_tasks_in_progress(userlist_job_progress)
    _hide_tasks_in_progress(userlist_overall_progress)


def clear_activity_tasks():
    _hide_tasks_in_progress(activity_counter)
    _hide_tasks_in_progress(activity_desc)


def clear_all_tasks():
    """Hides all tasks from all progress managers."""
    clear_activity_tasks()
    clear_api_tasks()
    clear_download_tasks()
    clear_metadata_tasks()
    clear_like_tasks()
    clear_userlist_tasks()


TASK_CLEAR_MAP = {
    "api": clear_api_tasks,
    "download": clear_download_tasks,
    "metadata": clear_metadata_tasks,
    "like": clear_like_tasks,
    "userlist": clear_userlist_tasks,
    "all": clear_all_tasks,
    "activity": clear_activity_tasks,
}


def clear_tasks_by_name(names: Union[str, List[str]]):
    """
    Calls the appropriate clear_..._tasks() function for each name provided.
    Accepts a single string or a list of strings.

    Args:
        names (Union[str, List[str]]): The name or names of the tasks to clear.

    Raises:
        ValueError: If any provided name is not a valid task type.
    """
    # 1. Normalize the input to always be a list
    if isinstance(names, str):
        names_to_clear = [names]
    else:
        # Assumes 'names' is a list or other iterable
        names_to_clear = names

    # 2. Loop through the list and process each name
    for name in names_to_clear:
        task_name = name.lower()
        clear_function = TASK_CLEAR_MAP.get(task_name)
        if clear_function:
            clear_function()
        else:
            # Raise an error on the first invalid name found
            raise ValueError(
                f"'{name}' is not a valid task type. "
                f"Valid options are: {list(TASK_CLEAR_MAP.keys())}"
            )
