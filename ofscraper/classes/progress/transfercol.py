from rich.progress import (
    TransferSpeedColumn,
)
from rich.text import Text
from ofscraper.utils.live.reader import get_multi_download_curr_jobs_speed
from rich.filesize import decimal

class OverallTransferSpeedColumn(TransferSpeedColumn):
    """Renders human readable transfer speed."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def render(self, task) -> Text:
            """Show data transfer speed."""
            speed = get_multi_download_curr_jobs_speed()
            if speed is None:
                return Text("?", style="progress.data.speed")
            data_speed = decimal(int(speed))
            return Text(f"{data_speed}/s", style="progress.data.speed")