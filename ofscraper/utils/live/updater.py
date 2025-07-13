from ofscraper.utils.live.progress import (
    activity_counter,
    activity_desc,
    api_job_progress,
    api_overall_progress,
    userlist_job_progress,
    userlist_overall_progress,
    metadata_overall_progress,
    download_job_progress,
    download_overall_progress,
    like_overall_progress,
)
from ofscraper.utils.live.tasks import (
    get_activity_counter_task,
    get_activity_task,
    get_user_task,
)


from rich.progress import Progress, TaskID


class ProgressManager:
    def __init__(self, job_progress: Progress, overall_progress: Progress):
        self.job = job_progress
        self.overall = overall_progress

    def add_job_task(self, *args, **kwargs) -> TaskID:
        return self.job.add_task(*args, **kwargs)

    def update_job_task(self, task_id: TaskID, *args, **kwargs):
        self.job.update(task_id, *args, **kwargs)

    def remove_job_task(self, task_id: TaskID):
        if task_id is None:
            return
        try:
            self.job.remove_task(task_id)
        except KeyError:
            pass

    def add_overall_task(self, *args, **kwargs) -> TaskID:
        return self.overall.add_task(*args, **kwargs)

    def update_overall_task(self, task_id: TaskID, *args, **kwargs):
        self.overall.update(task_id, *args, **kwargs)

    def remove_overall_task(self, task_id: TaskID):
        if task_id is None:
            return
        try:
            self.overall.remove_task(task_id)
        except KeyError:
            pass

    def clear(self):
        """Hides all tasks managed by this manager."""
        if self.job:
            for task in self.job.tasks:
                self.job.update(task.id, visible=False)
        if self.overall:
            for task in self.overall.tasks:
                self.overall.update(task.id, visible=False)


class ActivityManager:
    """Manages the unique activity description and counter progress bars."""

    def __init__(self, desc, counter, get_desc_id, get_counter_id, get_user_id):
        self.desc = desc
        self.counter = counter
        self.get_desc_id = get_desc_id
        self.get_counter_id = get_counter_id
        self.get_user_id = get_user_id

    def update_task(self, visible=True, **kwargs):
        """Updates the main activity description text."""
        self.desc.update(self.get_desc_id(), visible=visible, **kwargs)

    def update_overall(self, visible=True, **kwargs):
        """Updates the 'overall' progress bar (description, progress, total, etc.)."""

        self.counter.update(self.get_counter_id(), visible=visible, **kwargs)

    def update_user(self, visible=True, **kwargs):
        """Updates the 'user-specific' progress bar (description, progress, etc.)."""
        self.counter.update(self.get_user_id(), visible=visible, **kwargs)

    def get_description(self) -> str | None:
        """Gets the current description of the main activity task."""
        task_id = self.get_desc_id()
        # Find the full task object by its ID
        task = next((t for t in self.desc.tasks if t.id == task_id), None)
        return task.description if task else None


activity = ActivityManager(
    desc=activity_desc,
    counter=activity_counter,
    get_desc_id=get_activity_task,
    get_counter_id=get_activity_counter_task,
    get_user_id=get_user_task,
)

api = ProgressManager(api_job_progress, api_overall_progress)
userlist = ProgressManager(userlist_job_progress, userlist_overall_progress)
metadata = ProgressManager(None, metadata_overall_progress)
download = ProgressManager(download_job_progress, download_overall_progress)
like = ProgressManager(None, like_overall_progress)
