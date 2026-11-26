import cloup as click

after_action_script_option = click.option(
    "-aas",
    "--after-action-script",
    "after_action_script",
    help="Runs a script after an action for a model completes.",
)


post_script_option = click.option(
    "-ps",
    "--post-script",
    "post_script",
    help="Runs a script after processing all users (e.g. after a full scrape).",
)

alert_script_option = click.option(
    "--alert-script",
    "alert_script",
    help="Runs a script when something needs a person: login rejected, disk full, or a daemon pass failing.",
)

naming_script_option = click.option(
    "-ns",
    "--naming-script",
    "naming_script",
    help="Runs a script to generate the final filename or path for a media item.",
)

after_download_option = click.option(
    "-adl",
    "--after-download-script",
    "after_download_script",
    help="Runs a script after a download completes.",
)


skip_download_script = click.option(
    "-sdl",
    "--skip-download-script",
    "skip_download_script",
    help="Runs a script to decide whether to skip a download.",
)


retry_permanent_skips_option = click.option(
    "--retry-permanent-skips",
    "retry_permanent_skips",
    help="""
    \b
    Ask the skip download script again about the files it skipped for good
    (skip-permanent) for the creators in this run
    """,
    default=False,
    is_flag=True,
)
