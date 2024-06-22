import cloup as click
from ofscraper.utils.args.parse.arguments.logging import log_level_option,discord_log_level_option,console_output_level_option,console_rich_toggle
# Create the option group
logging_options = click.option_group(
    "Logging Options",
    log_level_option,
    discord_log_level_option,
    console_output_level_option,
    console_rich_toggle,
    help="Settings for logging",
)