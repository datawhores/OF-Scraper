import cloup as click

from ofscraper.utils.args.parse.arguments.download import (
    download_sem_option,
    download_threads_option,
    download_limit_option,
    show_download_bars_option,
    no_auto_resume_option,
)
download_options_desc="Download Options"
download_options_help="Options for downloads and download performance"
download_options = click.option_group(
    download_options_desc,
    no_auto_resume_option,
    show_download_bars_option,
    download_sem_option,
    download_threads_option,
    download_limit_option,
    help=download_options_help,
)
