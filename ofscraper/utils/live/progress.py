from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.style import Style
from rich.table import Column

import ofscraper.utils.console as console_
from ofscraper.classes.progress.progress import (
    MultiprocessFileProgress as MultiFileProgress,
    FileProgress,
    OverallFileProgress,
)
from ofscraper.classes.progress.transfercol import (
    OverallTransferSpeedColumn,
    TransferFileSpeedColumn,
)

# activity
activity_progress = Progress(
    TextColumn("[white]{task.description}[/white]"), refresh_per_second=2
)
activity_counter = Progress(
    TextColumn("[white]{task.description}[/white]"),
    BarColumn(table_column=Column(ratio=3), bar_width=100),
    MofNCompleteColumn(),
    refresh_per_second=2,
)

# download progress
download_job_progress = FileProgress(
    TextColumn("[white]{task.description}[/white]"),
    BarColumn(),
    TaskProgressColumn(),
    TransferFileSpeedColumn(),
    DownloadColumn(),
    console=console_.get_shared_console(),
    refresh_per_second=1.5,
    auto_refresh=True,
)

multi_download_job_progress = MultiFileProgress(
    TextColumn("[white]{task.description}[/white]", table_column=Column(ratio=2)),
    BarColumn(),
    TaskProgressColumn(),
    TransferFileSpeedColumn(),
    DownloadColumn(),
    refresh_per_second=3,
    auto_refresh=True,
)

download_overall_progress = OverallFileProgress(
    TextColumn("[white]{task.description}[/white]"),
    BarColumn(),
    TaskProgressColumn(),
    OverallTransferSpeedColumn(),
    TimeElapsedColumn(),
    refresh_per_second=3,
    auto_refresh=True,
)


metadata_overall_progress = OverallFileProgress(
    TextColumn("[white]{task.description}[/white]"),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    refresh_per_second=3,
    auto_refresh=True,
)


# user progress
userlist_overall_progress = Progress(
    SpinnerColumn(style=Style(color="blue")),
    TextColumn("[white]{task.description}[/white]"),
    refresh_per_second=5,
)
userlist_job_progress = Progress("[white]{task.description}[/white]")


# like progress

like_overall_progress = Progress(
    SpinnerColumn(style=Style(color="blue")),
    TextColumn("[white]{task.description}[/white]"),
    BarColumn(table_column=Column(ratio=2)),
    MofNCompleteColumn(),
    refresh_per_second=5,
)
# api
api_job_progress = Progress(
    "[white]{task.description}[/white]",
    console=console_.get_shared_console(),
    refresh_per_second=5,
)
api_overall_progress = Progress(
    SpinnerColumn(style=Style(color="blue")),
    TextColumn("[white]{task.description}[/white]"),
    console=console_.get_shared_console(),
    refresh_per_second=5,
)
