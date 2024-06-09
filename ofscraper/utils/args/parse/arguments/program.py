import re

import cloup as click
from humanfriendly import parse_size

from ofscraper.__version__ import __version__

version_option = click.version_option(
    __version__, "-v", "--version", package_name="OF-Scraper"
)

config_location_option = click.option(
    "-cg",
    "--config",
    help="Change location of config folder/file",
    default=None,
)

profile_option = click.option(
    "-r",
    "--profile",
    help="""
Change which profile you want to use
If not set then the config file is used
Profiles are always within the config file parent directory
""",
    default=None,
    callback=lambda ctx, param, value: (
        f"{re.sub('_profile','', value)}_profile" if value else None
    ),
)

# Create the option group

program_options = click.option_group(
    "Program Options",
    version_option,
    config_location_option,
    profile_option,
    help="Control the application's behavior with these settings",
)
