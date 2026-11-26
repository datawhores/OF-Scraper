import cloup as click

from ofscraper.utils.args.parse.arguments.automatic import (
    action_option,
    daemon_jitter_option,
    daemon_option,
    dry_run_json_option,
    dry_run_option,
    live_chat_option,
    live_interval_option,
    live_max_option,
    live_option,
    live_watch_option,
    profiles_option,
    refresh_users_option,
)

# Create the option group
automatic_options_desc = "Automation Options"
automatic_options_help = (
    "Control automated actions (like/unlike/download) and background execution"
)
automatic_options_tuple = (
    action_option,
    dry_run_option,
    dry_run_json_option,
    daemon_option,
    daemon_jitter_option,
    profiles_option,
    live_option,
    live_watch_option,
    live_interval_option,
    live_max_option,
    live_chat_option,
    refresh_users_option,
)
automatic_options = click.option_group(
    automatic_options_desc,
    *automatic_options_tuple,
    help=automatic_options_help,
)
