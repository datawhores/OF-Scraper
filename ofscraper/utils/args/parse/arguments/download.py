import cloup as click

no_auto_resume_option = click.option(
    "-ar",
    "--no-auto-resume",
    help="Cleanup temp .part files (removes resume ability)",
    default=False,
    is_flag=True,
)

show_download_bars_option = click.option(
    "-db",
    "--downloadbars",
    help="Show individual download progress bars",
    default=False,
    is_flag=True,
)

download_sem_option = click.option(
    "-sd",
    "--downloadsem",
    "--downloadsems",
     "--sems",
      "--sem",
    "downloadsem",
    help="Number of concurrent downloads per thread",
    default=None,
    type=int,
)

download_threads_option = click.option(
    "-dp",
    "--downloadthreads",
    "--threads",
    "--thread",
    "--downloadthread"
    "downloadthreads",
    help="Number of threads to use (minimum 1)",
    default=None,
    type=int,
)

