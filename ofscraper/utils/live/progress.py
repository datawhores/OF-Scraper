from rich.live import Live
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
        MofNCompleteColumn,

)
from rich.style import Style
from rich.table import Column

import ofscraper.utils.console as console_
from ofscraper.classes.multiprocessprogress import MultiprocessProgress as MultiProgress

#activity
activity_progress=Progress(
    TextColumn("[white]{task.description}[/white]"),
    TimeElapsedColumn(),
    )
activity_counter=Progress(
    TextColumn("[white]{task.description}[/white]"),
    BarColumn(table_column=Column(ratio=3),bar_width=100),
    MofNCompleteColumn())
                                                                                                        
#download progress
download_job_progress = Progress(
        TextColumn("[white]{task.description}[/white]"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console_.get_temp_console(),
)

download_overall_progress = Progress(
            TextColumn("[white]{task.description}[/white]"),
            BarColumn(),
            TaskProgressColumn(),
 )

multi_download_job_progress = MultiProgress(
                TextColumn("[white]{task.description}[/white]", table_column=Column(ratio=2)),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                TransferSpeedColumn(),
                DownloadColumn(),
)

live=Live( transient=False,refresh_per_second=4,console=console_.get_shared_console())  

#user progress
userlist_overall_progress=Progress(
                    SpinnerColumn(style=Style(color="blue")), TextColumn("[white]{task.description}[/white]")
)
userlist_job_progress = Progress("[white]{task.description}[/white]")
   

#like progress

like_overall_progress=Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("[white]{task.description}[/white]"),
        BarColumn(table_column=Column(ratio=2)),
        MofNCompleteColumn(),
)
#api
api_job_progress= Progress(
        "[white]{task.description}[/white]", console=console_.get_temp_console()
)
api_overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("[white]{task.description}[/white]"),
        console=console_.get_temp_console(),
    )