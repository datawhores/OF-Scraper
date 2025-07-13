import contextlib
import time
from typing import List, Union

import ofscraper.utils.console as console_
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.utils.live.groups import (
    activity_counter_group,
    activity_desc_counter_group,
    activity_desc_group,
    api_progress_group,
    get_download_group,
    like_progress_group,
    metadata_group,
    userlist_group,
)
from ofscraper.utils.live.live import get_live, stop_live

from ofscraper.utils.live.clear import clear_tasks_by_name
from ofscraper.utils.live.updater import ActivityManager


@contextlib.contextmanager
def stop_live_screen(revert=True, clear=None):
    old_render = get_live().renderable
    stop_live()
    console_.get_console().clear_live()
    ##give time for console to clear
    time.sleep(0.3)
    yield
    if revert and old_render:
        get_live().update(old_render)
    elif clear:
        clear_tasks_by_name(clear)


SCREENS = {
    "download": {
        "layout": get_download_group(),
        "clear": "download",
        "suppress": "SUPRESS_DOWNLOAD_DISPLAY",
    },
    "api": {
        "layout": api_progress_group,
        "clear": "api",
        "suppress": "SUPRESS_API_DISPLAY",
    },
    "like": {
        "layout": like_progress_group,
        "clear": "like",
        "suppress": "SUPRESS_LIKE_DISPLAY",
    },
    "user_list": {
        "layout": userlist_group,
        "clear": "userlist",
        "suppress": "SUPRESS_SUBSCRIPTION_DISPLAY",
    },
    "metadata": {
        "layout": metadata_group,
        "clear": "metadata",
        "suppress": "SUPRESS_DOWNLOAD_DISPLAY",
    },
    "main_activity": {
        "layout": activity_desc_counter_group,
        "clear": "all",
    },
    "manual": {"layout": activity_desc_group, "suppress": "SUPRESS_API_DISPLAY"},
    "activity_desc": {
        "layout": activity_desc_group,
        "suppress": "SUPRESS_API_DISPLAY",
        # No "clear" key means tasks won't be cleared on exit
    },
    "activity_counter": {
        "layout": activity_counter_group,
        "suppress": "SUPRESS_API_DISPLAY",
    },
}


def setup_live(screen_name: str, revert=True, clear=True):
    """
    A single function to set up any live screen layout.
    The 'clear' flag overrides the default screen config.
    The 'revert' flag reverts to the previous screen
    """
    config = SCREENS.get(screen_name.lower())
    if not config:
        raise ValueError(f"Unknown screen: '{screen_name}'.")

    # Use the 'clear' instruction from the config only if the flag is True
    clear_instruction = config.get("clear") if clear else None

    return ProgressLayoutManager(
        layout=config["layout"],
        clear_on_exit=clear_instruction,  # Pass the final instruction
        supress_key=config.get("suppress"),
        revert=revert,
    )


class ProgressLayoutManager:
    def __init__(self, layout, clear_on_exit=None, supress_key=None, revert=True):
        self.live = get_live()
        self.layout = layout
        self.clear_on_exit = clear_on_exit
        self.supress_key = supress_key
        self.previous_layout = None
        self.revert = revert

    def __enter__(self):
        self.previous_layout = self.live.renderable
        if self.supress_key:
            console_.get_shared_console().quiet = (
                of_env.getattr(self.supress_key)
                if of_env.getattr(self.supress_key) is not None
                else console_.get_shared_console().quiet
            )
        if not self.live.is_started:
            self.live.start()
        self.live.update(self.layout, refresh=True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.previous_layout and self.revert:
            self.live.update(self.previous_layout, refresh=True)
        if self.clear_on_exit:
            clear_tasks_by_name(self.clear_on_exit)


class TemporaryTaskState:
    """A context manager to snapshot and restore the state of multiple tasks."""

    def __init__(
        self, activity_manager: ActivityManager, *task_types: Union[str, List[str]]
    ):
        """
        Initializes the state manager.

        Args:
            activity_manager (ActivityManager): The manager instance controlling the tasks.
            *task_types: The names of the tasks to manage. Can be passed in two ways:
                         1. As separate string arguments: TemporaryTaskState(activity, "main", "user")
                         2. As a single list of strings: TemporaryTaskState(activity, ["main", "user"])
                         Valid options are "main", "overall", "user". Defaults to ("main",) if empty.
        """
        # This logic handles both calling styles
        if len(task_types) == 1 and isinstance(task_types[0], list):
            self.task_types: List[str] = task_types[0]  # Unpack the list from the tuple
        else:
            self.task_types: tuple[str, ...] = (
                task_types if task_types else ("main",)
            )  # Use the tuple directly

        self.manager = activity_manager
        self.previous_states = {}

    def _get_task_info(self, task_type: str) -> tuple:
        """Helper to get the right objects based on task type."""
        if task_type == "main":
            return (
                self.manager.desc,
                self.manager.update_task,
                self.manager.get_desc_id(),
            )
        elif task_type == "overall":
            return (
                self.manager.counter,
                self.manager.update_overall,
                self.manager.get_counter_id(),
            )
        elif task_type == "user":
            return (
                self.manager.counter,
                self.manager.update_user,
                self.manager.get_user_id(),
            )
        return (None, None, None)

    def __enter__(self) -> "TemporaryTaskState":
        for task_type in self.task_types:
            progress_obj, _, task_id = self._get_task_info(task_type)
            if not progress_obj:
                continue
            task = next((t for t in progress_obj.tasks if t.id == task_id), None)
            if task:
                self.previous_states[task_type] = {
                    "description": task.description,
                    "completed": task.completed,
                    "total": task.total,
                    "visible": task.visible,
                }
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        for task_type, state in self.previous_states.items():
            _, update_method, _ = self._get_task_info(task_type)
            if update_method:
                update_method(**state)


class TaskLock:
    """
    A context manager to temporarily block updates for specific task types
    on an ActivityManager instance.
    """

    def __init__(
        self, activity_manager: "ActivityManager", *task_types: Union[str, List[str]]
    ):
        """
        Initializes the task lock.

        Args:
            activity_manager (ActivityManager): The manager instance to lock.
            *task_types: The names of the tasks to lock ("main", "overall", "user").
                         If not provided, all tasks will be locked.
        """
        if len(task_types) == 1 and isinstance(task_types[0], list):
            self.task_types = task_types[0]
        else:
            # If no types are given, default to locking all of them
            self.task_types = task_types if task_types else ["main", "overall", "user"]

        self.manager = activity_manager
        self.original_methods = {}
        # Map task types to the method names that update them
        self.method_map = {
            "main": "update_task",
            "overall": "update_overall",
            "user": "update_user",
        }

    def __enter__(self):
        def no_op(*args, **kwargs):
            pass

        # For each specified task type, find its update method and replace it
        for task_type in self.task_types:
            method_name = self.method_map.get(task_type)
            if method_name and hasattr(self.manager, method_name):
                self.original_methods[method_name] = getattr(self.manager, method_name)
                setattr(self.manager, method_name, no_op)

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore all the original methods that were saved
        for method_name, original_method in self.original_methods.items():
            setattr(self.manager, method_name, original_method)
