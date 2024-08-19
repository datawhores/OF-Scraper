from rich.progress import (
    TransferSpeedColumn,
)
from rich.text import Text
import ofscraper.utils.live.progress as progress_utils
from rich.filesize import decimal


class OverallTransferSpeedColumn(TransferSpeedColumn):
    """Renders human readable transfer speed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._process_list = None

    def render(self, task) -> Text:
        """Show data transfer speed."""
        speed = self._get_curr_speed_helper(task)
        if not speed:
            return Text("?", style="progress.data.speed")
        data_speed = decimal(int(speed))
        return Text(f"{data_speed}/s", style="progress.data.speed")

    def _get_curr_speed_helper(self, task):
        return progress_utils.download_overall_progress.speed


class TransferFileSpeedColumn(TransferSpeedColumn):
    """Renders human readable transfer speed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._process_list = None

    def render(self, task) -> Text:
        """Show data transfer speed."""
        speed = task.speed_via_file
        if not speed:
            return Text("?", style="progress.data.speed")
        data_speed = decimal(int(speed))
        return Text(f"{data_speed}/s", style="progress.data.speed")
