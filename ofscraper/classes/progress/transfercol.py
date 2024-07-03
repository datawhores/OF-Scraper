from rich.progress import (
    TransferSpeedColumn,
)
from rich.text import Text
from ofscraper.utils.live.reader import get_multi_download_curr_jobs_speed_bars
from rich.filesize import decimal

class OverallTransferSpeedColumn(TransferSpeedColumn):
    """Renders human readable transfer speed."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def render(self, task) -> Text:
            """Show data transfer speed."""
            speed = self._get_curr_speed_helper()
            if not speed:
                return Text("?", style="progress.data.speed")
            data_speed = decimal(int(speed))
            return Text(f"{data_speed}/s", style="progress.data.speed")
    def _get_curr_speed_helper(self):
        return get_multi_download_curr_jobs_speed_bars()


class TransferFileSpeedColumn(TransferSpeedColumn):
    """Renders human readable transfer speed."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def render(self, task) -> Text:
            """Show data transfer speed."""
            speed = task.speed_via_file
            if not speed:
                return Text("?", style="progress.data.speed")
            data_speed = decimal(int(speed))
            return Text(f"{data_speed}/s", style="progress.data.speed")