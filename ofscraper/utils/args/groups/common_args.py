import functools
import itertools
import re

import cloup as click
from humanfriendly import parse_size

import ofscraper.utils.args.helpers as helpers
from ofscraper.__version__ import __version__
from ofscraper.const.constants import KEY_OPTIONS


def common_params(func):

    @click.option_group(
        "Program Options",
        click.version_option(__version__, "-v", "--version", package_name="OF-Scraper"),
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
        "Download Options",
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
            "--downloadsem",
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
        help="Options for downloads and download performance",
    )
    @click.option_group(
        "Metadata Options",
        click.option(
            "-md",
            "--metadata",
            "metadata",
            help="""
            \b
            Skip media downloads and gather metadata only 
            [no change to download status] 
            [select one --metadata or --metadata-update or --metadata-complete]""",
            flag_value="none",  # Enforce "none" as the only valid value
        ),
        click.option(
            "-mu",
            "--metadata-update",
            "metadata",
            help="""
            \b
            Skip media downloads, gather metadata, and update download status based on file presence 
            [select one --metadata or --metadata-update or --metadata-complete]""",
            flag_value="file",
        ),
        click.option(
            "-mc",
            "--metadata-complete",
            "metadata",
            help="""
            \b
            Skip media downloads, gather metadata, and mark all media as downloaded 
            [select one --metadata or --metadata-update or --metadata-complete]""",
            flag_value="complete",
        ),
        help="Options generating metadata",
    )
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper


def common_advanced_params(func):
    @click.option_group(
        "Advanced Program Options",
        click.option(
            "-nc",
            "--no-cache",
            help="Disable cache and forces consecutive api scan",
            default=False,
            is_flag=True,
        ),
        click.option(
            "-nca",
            "--no-api-cache",
            help="Forces consecutive api scan",
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
            type=click.Choice(["dc", "deviint", "sneaky"], case_sensitive=False),
            callback=lambda ctx, param, value: value.lower() if value else None,
        ),
        click.option(
            "-up",
            "--update-profile",
            help="Get up-to-date profile info instead of using cache",
            default=False,
            is_flag=True,
        ),
        click.option(
            "-ds",
            "--download-script",
            "download_script",
            help="""
            \b
            runs a script post model download
            addional args sent to script username, model_id, media json ,and post json
            """,
        ),
        help="Advanced control of program behavior",
    )
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper


def common_other_params(func):
    @click.option_group(
        "Media Filters",
        click.option(
            "-q",
            "--quality",
            type=click.Choice(["240", "720", "source"], case_sensitive=False),
        ),
        click.option(
            "-mt",
            "--mediatype",
            help="Filter by media type (Videos, Audios, Images)",
            default=[],
            required=False,
            type=helpers.mediatype_helper,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
            multiple=True,
        ),
        click.option(
            "-sx",
            "--size-max",
            help="Filter out files larger than the given size (bytes or human-readable, e.g., 10mb)",
            required=False,
            type=parse_size,
        ),
        click.option(
            "-sm",
            "--size-min",
            help="Filter out files smaller than the given size (bytes or human-readable, e.g., 10mb)",
            required=False,
            type=parse_size,
        ),
        help="Options for controlling which media is downloaded",
    )
    @click.option_group(
        "Filename Modification options",
        click.option(
            "-g",
            "--original",
            help="Don't truncate long paths",
            is_flag=True,
        ),
        click.option(
            "-tt",
            "--text-type",
            help="set length based on word or letter",
            type=click.Choice(["word", "letter"], case_sensitive=False),
            default="word",
        ),
        click.option(
            "-sr",
            "--space-replacer",
            help="character to replace spaces with",
        ),
        click.option("-tl", "--textlength", help="max length of text", type=click.INT),
        help="""
\b
Options for controlling the output of the final filename after placeholders are replaced
""",
    )
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
