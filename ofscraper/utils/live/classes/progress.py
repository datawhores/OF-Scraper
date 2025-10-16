from typing import Any, NewType, Optional
import rich.progress
from ofscraper.utils.live.classes.task import Task
import ofscraper.utils.live.progress as progress_utils

TaskID = NewType("TaskID", int)



class FileProgress(rich.progress.Progress):
    def __init__(self, *args, **kwargs) -> None:
        self._files = {}
        self._last_updated = {}
        super().__init__(*args, **kwargs)

    def get_file(self, taskID):
        return self._files.get(taskID)

    def add_task(
        self,
        description: str,
        start: bool = True,
        total: Optional[float] = 100.0,
        completed: int = 0,
        visible: bool = True,
        file=None,
        **fields: Any,
    ) -> TaskID:
        """Add a new 'task' to the Progress display.

        Args:
            description (str): A description of the task.
            start (bool, optional): Start the task immediately (to calculate elapsed time). If set to False,
                you will need to call `start` manually. Defaults to True.
            total (float, optional): Number of total steps in the progress if known.
                Set to None to render a pulsing animation. Defaults to 100.
            completed (int, optional): Number of steps completed so far. Defaults to 0.
            visible (bool, optional): Enable display of the task. Defaults to True.
            **fields (str): Additional data fields required for rendering.

        Returns:
            TaskID: An ID you can use when calling `update`.
        """
        with self._lock:
            task = Task(
                self._task_index,
                description,
                total,
                completed,
                visible=visible,
                fields=fields,
                _get_time=self.get_time,
                _lock=self._lock,
                file=file,
            )
            task.progress_parent = self
            self._tasks[self._task_index] = task
            if start:
                self.start_task(self._task_index)
            new_task_index = self._task_index
            self._task_index = TaskID(int(self._task_index) + 1)
        self.refresh()
        return new_task_index

class OverallFileProgress(rich.progress.Progress):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def get_file(self, taskID):
        return self._files.get(taskID)

    def add_task(
        self,
        description: str,
        start: bool = True,
        total: Optional[float] = 100.0,
        completed: int = 0,
        visible: bool = True,
        **fields: Any,
    ) -> TaskID:
        """Add a new 'task' to the Progress display..

        Args:
            description (str): A description of the task.
            start (bool, optional): Start the task immediately (to calculate elapsed time). If set to False,
                you will need to call `start` manually. Defaults to True.
            total (float, optional): Number of total steps in the progress if known.
                Set to None to render a pulsing animation. Defaults to 100.
            completed (int, optional): Number of steps completed so far. Defaults to 0.
            visible (bool, optional): Enable display of the task. Defaults to True.
            **fields (str): Additional data fields required for rendering.

        Returns:
            TaskID: An ID you can use when calling `update`.
        """
        id = super().add_task(description, start, total, completed, visible, **fields)
        task = self._tasks[id]
        self._tasks[id] = task
        return id

    @property
    def speed(self):
        return sum([ele.speed_via_file or 0 for ele in self.download_tasks])

    @property
    def download_tasks(self):
        return (
            progress_utils.download_job_progress.tasks
        )
