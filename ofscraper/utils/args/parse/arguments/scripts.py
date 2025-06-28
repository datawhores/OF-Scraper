import cloup as click

download_script_option = click.option(
    "-dls",
    "--download-script",
    "download_script",
    help="""
    \b
    Runs a script after a model's media and posts have been downloaded.
    The script receives a JSON dictionary via standard input (stdin) with the following keys:
    - username: The model's username (string).
    - model_id: The model's ID (integer).
    - media: A list of dictionaries, each representing a downloaded media item.
    - posts: A list of dictionaries, each representing a post associated with the media.
    - userdata: A dictionary containing the model's user data.
    The script can then perform custom actions.
    """
)


post_script_option = click.option(
    "-ps",
    "--post-script",
    "post_script",
    help="""
    \b
    Runs a script after processing all users (e.g., after a full scrape operation).
    The script receives a JSON dictionary via standard input (stdin) with the following keys:
    - process_users: A dictionary of processed users where keys are usernames (strings) and values are the corresponding model's user data dictionaries.
    - unprocess_users: A dictionary of unprocessed users where keys are usernames (strings) and values are the corresponding model's user data dictionaries.

    The script can use this aggregated data for custom reporting, archiving, or other tasks.
    """
)

naming_script_option = click.option(
    "-ns",
    "--naming-script",
    "naming_script",
    help="""
    \b
    Runs a script to dynamically generate the final filename or path for a media item.
    The script receives a JSON dictionary via standard input (stdin) with the following keys:
    - media: A dictionary representing the media item, including its ID, type, temporary paths, and other attributes.
    - dir_format: The current directory format string (string).
    - file_format: The current file format string (string).
    - metadata: The current metadata format setting (string).
    The script is expected to output the desired final filename or full path via standard output (stdout).
    """
)