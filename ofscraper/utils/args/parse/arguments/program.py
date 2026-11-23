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
    # type=click.Path(exists=False, dir_okay=True, readable=True),
    default=None,
)


profile_option = click.option(
    "-r",
    "--profile",
    help="""
Change which profile to use.
If not set, the default profile from config.json is used.
Profiles are always inside the config.json parent directory.
""",
    default=None,
    callback=lambda ctx, param, value: (
        f"{re.sub('_profile','', value)}_profile" if value else None
    ),
)
site_option = click.option(
    "--site",
    help="""
Site to use for this run: onlyfans or fansly.
If not set, the profile's site.json decides, and OnlyFans is the default.
""",
    type=click.Choice(["onlyfans", "fansly"], case_sensitive=False),
    default=None,
)
env_file_option = click.option(
    "--env-files",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Environment file to load (.env, .yaml/.yml or .json). Can be given more than once; later files win.",
    default=None,
    multiple=True,
)
