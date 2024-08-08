import cloup as click

from ofscraper.utils.args.parse.arguments.program import (
    config_location_option,
    profile_option,
    version_option,
)

program_options_desc="Program Options"
program_options_help="Control the application's behavior with these settings"
# Create the option group
program_options = click.option_group(
    program_options_desc,
    version_option,
    config_location_option,
    profile_option,
    help=program_options_help,
)
