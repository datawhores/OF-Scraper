import cloup as click

after_action_script_option = click.option(
    "-dls",
    "--downloads-finish-script",
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
    "ater_download_script",
    help="""
    \b
    Runs script after download has completed
    """,
)


download_skip_script = click.option(
    "-dlt",
    "--download-skip-script",
    "download_skip_script",
    help="""
    \b
    Runs a script to dynamically skip a download
    """,
)
