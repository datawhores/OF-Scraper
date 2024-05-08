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
    help="Number of concurrent downloads per thread",
    default=None,
    type=int,
)

download_threads_option = click.option(
    "-dp",
    "--downloadthreads",
    help="Number of threads to use (minimum 1)",
    default=None,
    type=int,
)

# Create the option group

download_options = click.option_group(
    "Download Options",
    no_auto_resume_option,
    show_download_bars_option,
    download_sem_option,
    download_threads_option,
    help="Options for downloads and download performance",
)
