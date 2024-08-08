import re

import cloup as click

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
If not set then the default profile is used, based on the config.json file
Profiles are always within the config.json file parent directory
""",
    default=None,
    callback=lambda ctx, param, value: (
        f"{re.sub('_profile','', value)}_profile" if value else None
    ),
)
