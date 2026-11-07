import cloup as click

from ofscraper.utils.args.parse.arguments.automatic import (
    action_option,
    daemon_option,
    live_chat_option,
    live_interval_option,
    live_max_option,
    live_option,
    live_watch_option,
)

# Create the option group
automatic_options_desc = "Automation Options"
automatic_options_help = (
    "Control automated actions (like/unlike/download) and background execution"
)
automatic_options_tuple = (
    action_option,
    daemon_option,
    live_option,
    live_watch_option,
    live_interval_option,
    live_max_option,
    live_chat_option,
)
automatic_options = click.option_group(
    automatic_options_desc,
    *automatic_options_tuple,
    help=automatic_options_help,
)
