import cloup as click
from ofscraper.utils.args.parse.arguments.program import version_option,config_location_option,profile_option
# Create the option group
program_options = click.option_group(
    "Program Options",
    version_option,
    config_location_option,
    profile_option,
    help="Control the application's behavior with these settings",
)