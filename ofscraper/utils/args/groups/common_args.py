import functools
import itertools
import re

import cloup as click

import ofscraper.utils.args.helpers as helpers
from ofscraper.__version__ import __version__
from ofscraper.const.constants import KEY_OPTIONS


def common_params(func):

    @click.option_group(
        "Program Options",
        click.version_option(version=__version__),
        click.option(
            "-cg",
            "--config",
            help="Change location of config folder/file",
            default=None,
        ),
        click.option(
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
        ),
        help="Control the application's behavior with these settings",
    )
    @click.option_group(
        "Logging Options",
        click.option(
            "-l",
            "--log",
            help="Set log file level",
            type=click.Choice(
                ["OFF", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
                case_sensitive=False,
            ),
            default=None,
            callback=lambda ctx, param, value: value.upper() if value else None,
        ),
        click.option(
            "-dc",
            "--discord",
            help="Set discord log level",
            type=click.Choice(
                ["OFF", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
                case_sensitive=False,
            ),
            default="OFF",
            callback=lambda ctx, param, value: value.upper() if value else None,
        ),
        click.option(
            "-p",
            "--output",
            help="Set console output log level",
            type=click.Choice(
                ["PROMPT", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
                case_sensitive=False,
            ),
            default="NORMAL",
            callback=lambda ctx, param, value: value.upper() if value else None,
        ),
        help="Settings for logging",
    )
    @click.option_group(
        "Advanced Program Options",
        click.option(
            "-nc",
            "--no-cache",
            help="Disable cache",
            default=False,
            is_flag=True,
        ),
        click.option(
            "-k",
            "--key-mode",
            help="Key mode override",
            default=None,
            type=click.Choice(KEY_OPTIONS),
        ),
        click.option(
            "-dr",
            "--dynamic-rules",
            help="Dynamic signing",
            default=None,
            type=click.Choice(["dc", "deviint"], case_sensitive=False),
            callback=lambda ctx, param, value: value.lower() if value else None,
        ),
        click.option(
            "-ar",
            "--no-auto-resume",
            help="Cleanup temp .part files (removes resume ability)",
            default=False,
            is_flag=True,
        ),
        click.option(
            "-db",
            "--downloadbars",
            help="Show individual download progress bars",
            default=False,
            is_flag=True,
        ),
        click.option(
            "-sd",
            "--downloadsems",
            help="Number of concurrent downloads per thread",
            default=None,
            type=int,
        ),
        click.option(
            "-dp",
            "--downloadthreads",
            help="Number of threads to use (minimum 1)",
            default=None,
            type=int,
        ),
        click.option(
            "-up",
            "--update-profile",
            help="Get up-to-date profile info instead of cache",
            default=False,
            is_flag=True,
        ),
        click.option(
            "-md",
            "--metadata",
            "metadata",
            help="""
            \b
            Skip media downloads and gather metadata only 
            [no change to download status] 
            [select onw one --metadata or --metadata-update or --metadata-complete]""",
            flag_value="none",  # Enforce "none" as the only valid value
        ),
        click.option(
            "-mu",
            "--metadata-update",
            "metadata",
            help="""
            \b
            Skip media downloads, gather metadata, and update download status based on file presence 
            [select onw one --metadata or --metadata-update or --metadata-complete]""",
            flag_value="file",
        ),
        click.option(
            "-mc",
            "--metadata-complete",
            "metadata",
            help="""
            \b
            Skip media downloads, gather metadata, and mark all media as downloaded 
            [select onw one --metadata or --metadata-update or --metadata-complete]""",
            flag_value="complete",
        ),
        help="Advanced control of program behavior",
    )
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper


def common_other_params(func):
    click.option_group(
        "Downloading options",
        click.option(
            "-g",
            "--original",
            help="Don't truncate long paths",
            is_flag=True,  
        ),
        click.option(
            "-q",
            "--quality",
            type=click.Choice(["240", "720", "source"], case_sensitive=False),
        ),
        click.option(
            "-lb",
            "--label",
            help="Filter by label (use helpers.label_helper to process)",
            default=[],
            required=False,
            type=helpers.label_helper,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
            multiple=True,
        ),
        help="Options for controlling download behavior",
    )

    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
