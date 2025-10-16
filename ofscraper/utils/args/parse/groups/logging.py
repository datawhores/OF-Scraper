import cloup as click

from ofscraper.utils.args.parse.arguments.logging import (
    console_output_level_option,
    console_rich_toggle,
    discord_log_level_option,
    log_level_option,
)

logging_options_desc = "Logging Options"
logging_options_help = "Settings for logging"
logging_options_tuple = (
    console_output_level_option,
    console_rich_toggle,
    discord_log_level_option,
    log_level_option,
)

# Create the option group
logging_options = click.option_group(
    "Logging Options",
    *logging_options_tuple,
    help=logging_options_help,
)
