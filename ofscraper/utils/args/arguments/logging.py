import cloup as click

log_level_option = click.option(
    "-l",
    "--log",
    help="Set log file level",
    type=click.Choice(
        ["OFF", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
        case_sensitive=False,
    ),
    default=None,
    callback=lambda ctx, param, value: value.upper() if value else None,
)

discord_log_level_option = click.option(
    "-dc",
    "--discord",
    help="Set discord log level",
    type=click.Choice(
        ["OFF", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
        case_sensitive=False,
    ),
    default="OFF",
    callback=lambda ctx, param, value: value.upper() if value else None,
)

console_output_level_option = click.option(
    "-p",
    "--output",
    help="Set console output log level",
    type=click.Choice(
        ["PROMPT", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
        case_sensitive=False,
    ),
    default="NORMAL",
    callback=lambda ctx, param, value: value.upper() if value else None,
)

# Create the option group

logging_options = click.option_group(
    "Logging Options",
    log_level_option,
    discord_log_level_option,
    console_output_level_option,
    help="Settings for logging",
)