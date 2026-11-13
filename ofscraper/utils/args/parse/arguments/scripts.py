import cloup as click

after_action_script_option = click.option(
    "-aas",
    "--after-action-script",
    "after_action_script",
    help="""
    \b
    Runs a script after an action for a model has completed.
    """,
)


post_script_option = click.option(
    "-ps",
    "--post-script",
    "post_script",
    help="""
    \b
    Runs a script after processing all users (e.g., after a full scrape operation)
    """,
)

naming_script_option = click.option(
    "-ns",
    "--naming-script",
    "naming_script",
    help="""
    \b
    Runs a script to dynamically generate the final filename or path for a media item.
    """,
)

after_download_option = click.option(
    "-adl",
    "--after-download-script",
    "after_download_script",
    help="""
    \b
    Runs script after download has completed
    """,
)


skip_download_script = click.option(
    "-sdl",
    "--skip-download-script",
    "skip_download_script",
    help="""
    \b
    Runs a script to dynamically skip a download
    """,
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
