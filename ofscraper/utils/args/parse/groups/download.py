import cloup as click
from ofscraper.utils.args.parse.arguments.download import no_auto_resume_option,show_download_bars_option,download_sem_option,download_threads_option
download_options = click.option_group(
    "Download Options",
    no_auto_resume_option,
    show_download_bars_option,
    download_sem_option,
    download_threads_option,
    help="Options for downloads and download performance",
)