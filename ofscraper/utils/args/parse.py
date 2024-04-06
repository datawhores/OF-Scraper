import argparse
import functools
import itertools
import re
import sys

import cloup as click

# import click
from humanfriendly import parse_size

import ofscraper.utils.args.helpers as helpers
import ofscraper.utils.args.write as write_args
import ofscraper.utils.system.system as system
from ofscraper.__version__ import __version__
from ofscraper.const.constants import KEY_OPTIONS


class AutoDotDict(dict):
    """
    Class that automatically converts a dictionary to an object-like structure
    with dot notation access for top-level keys.
    """

    def __getattr__(self, attr):
        """
        Overrides getattr to access dictionary keys using dot notation.
        Raises AttributeError if the key is not found.
        """
        try:
            return self.get(attr)
        except KeyError:
            raise AttributeError(f"Attribute '{attr}' not found")

    def __setattr__(self, attr, value):
        """
        Overrides setattr to set values using dot notation.
        """
        self[attr] = value


def common_params(func):

    @click.option_group(
        "global",
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
        help="global options for all commands",
    )
    @click.option_group(
        "output",
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
        help="Settigns for logging",
    )
    @click.option_group(
        "advanced args",
        click.option(
            "-uf",
            "--users-first",
            help="Scrape all users first rather than one at a time (affects --action)",
            default=False,
            is_flag=True,  # Shorthand for action="store_true"
        ),
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
        click.constraints.mutually_exclusive(
            click.option(
                "-fi",
                "--individual",
                help="Search each username as a separate request when --username is provided",
                default=False,
                is_flag=True,
            ),
            click.option(
                "-fl",
                "--list",
                help="Search entire enabled lists before filtering for usernames when --username is provided",
                default=False,
                is_flag=True,
            ),
        ),
        click.option(
            "-md",
            "--metadata",
            "metadata",
            help="Skip media downloads and gather metadata only (no change to download status)",
            flag_value="none",  # Enforce "none" as the only valid value
        ),
        click.option(
            "-mu",
            "--metadata-update",
            "metadata",
            help="Skip media downloads, gather metadata, and update download status based on file presence",
            flag_value="file",
        ),
        click.option(
            "-mc",
            "--metadata-complete",
            "metadata",
            help="Skip media downloads, gather metadata, and mark all media as downloaded",
            flag_value="complete",
        ),
        help="advanced global args for all commands",
    )
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper


def common_other_params(func):
    click.option_group(
    "download options",
    click.option(
        "-g",
        "--original",
        help="Don't truncate long paths",
        is_flag=True,  # Use `is_flag=True` for boolean flags
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
    default=None,
    required=False,
    type=helpers.label_helper,
    callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
    ),
    multiple=True,
),
    help="Scraper options specific to downloading"
    )


    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper


@click.group(
    help="Program Args",
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True,
    )
@click.option_group(
    "posts",
    click.option(
        "-q",
        "--quality",
        type=click.Choice(["240", "720", "source"], case_sensitive=False),
    ),
    click.option(
        "-o",
        "--posts",
        help="""
        Select areas for batch actions (comma or space separated).
        Options: HighLights, Archived, Messages, Timeline, Pinned, Stories, Purchased, Profile, Labels, All
        """,
        default=None,
        required=False,
        type=helpers.posttype_helper,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
        multiple=True,
    ),
    click.option(
        "-da",
        "--download-area",
        "download_area",
        help="""
        Perform download in specified areas (comma or space separated).
        Options: HighLights, Archived, Messages, Timeline, Pinned, Stories, Purchased, Profile, Labels, All
        Has preference over --posts
        """,
        default=None,
        required=False,
        type=helpers.download_helper,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
        multiple=True,
    ),
    click.option(
        "-la",
        "--like-area",
        help="""
        Perform like/unlike in selected areas (comma or space separated).
        Options: Archived, Timeline, Pinned, Labels, All
        Has preference over --posts
        """,
        default=None,
        required=False,
        type=helpers.like_helper,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
        multiple=True,
    ),
    click.option(
        "-ft",
        "--filter",
        help="Filter posts by regex (case-sensitive if uppercase characters included)",
        default=".*",
        required=False,
        type=str,
    ),
    click.option(
        "-nf",
        "--neg-filter",
        help="Filter posts to exclude those matching regex (case-sensitive if uppercase characters included)",
        default=None,
        required=False,
        type=str,
    ),
    click.option(
        "-sp",
        "--scrape-paid",
        help="Scrape entire paid page (can take a very long time)",
        default=False,
        is_flag=True,
    ),
    click.option(
        "-xc",
        "--max-count",
        help="Maximum number of posts to download (oldest non-duped first)",
        default=0,
        type=int,
    ),
    click.option(
        "-it",
        "--item-sort",
        help="Change item/post order before action (default: date asc or random)",
        default=None,
        required=False,
        type=click.Choice(
            [
                "random",
                "text-asc",
                "text-desc",
                "date-asc",
                "date-desc",
                "filename-asc",
                "filename-desc",
            ]
        ),

    ),
    click.constraints.mutually_exclusive(
        click.option(
        "-e",
        "--force-all",
        help="Download all files regardless of database presence",
        default=False,
        is_flag=True,
        ),
    click.option(
    "-eq",
    "--force-model-unique",
    help="Only download files not present for the current model in the database",
    default=False,
    is_flag=True,
)),


    click.constraints.mutually_exclusive(
click.option(
    "-to",
    "--protected-only",
    help="Only download content that requires decryption",
    default=False,
    is_flag=True,
),
click.option(
    "-no",
    "--normal-only",
    help="Only download content that does not require decryption",
    default=False,
    is_flag=True,
),
click.option(
    "-lb",
    "--label",
    help="Filter by label (use helpers.label_helper to process)",
    default=None,
    required=False,
    type=helpers.label_helper,
    callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
    ),
    multiple=True,
)
,click.option(
    "-be",
    "--before",
    help="Process posts at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=helpers.arrow_helper,
)
,click.option(
    "-af",
    "--after",
    help="Process posts at or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=helpers.arrow_helper,
)
,click.option(
    "-mt",
    "--mediatype",
    help="Filter by media type (Videos, Audios, Images)",
    default=[],
    required=False,
    type=helpers.mediatype_helper,
    callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    multiple=True,
)
,click.option(
    "-sx",
    "--size-max",
    help="Filter out files larger than the given size (bytes or human-readable, e.g., 10mb)",
    required=False,
    type=parse_size,
)
,click.option(
    "-sm",
    "--size-min",
    help="Filter out files smaller than the given size (bytes or human-readable, e.g., 10mb)",
    required=False,
    type=parse_size,
),

click.option(
    "-mm/-ms",
    "--mass-only/--mass-skip",
    "mass_msg",
    help="Flag for downloading mass content or promos",
    default=None,
    required=False,

),


click.option(
    "-ok/-sk",
    "--only-timed/--skip-timed",
    "timed_only",
    default=None,
    help="Download only promotional or temporary posts",
)

),

    help="options for posts",
 )
@click.option_group(
    "scraper",
    click.option(
        "-u",
        "--usernames",
        help="Select which username to process (name,name2). Set to ALL for all users.",
        type=helpers.username_helper,  # Assuming you'll still use this helper function
        multiple=True,  # Use `multiple=True` for accepting multiple values
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
    click.option(
        "-eu",
        "--excluded-username",
        help="Select which usernames to exclude (name,name2). Has preference over --username.",
        type=helpers.username_helper,
        multiple=True,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
    click.option(
        "-d",
        "--daemon",
        help="Run script in the background. Set value to minimum minutes between script runs. Overdue runs will run as soon as previous run finishes.",
        type=float,
    ),
    click.option(
        "-g",
        "--original",
        help="Don't truncate long paths",
        is_flag=True,  # Use `is_flag=True` for boolean flags
    ),
    click.option(
        "-a",
        "--action",
        help="""
    Select batch action(s) to perform [like,unlike,download].
    Accepts space or comma-separated list. Like and unlike cannot be combined.
    """,
        multiple=True,
        callback=lambda ctx, param, value: (
            helpers.action_helper(value) if value else None
        ),
    ),
    help="Scraping options",
)
@click.option_group(
    "user filters",
    click.option(
        "-cp",
        "--current-price",
        help="Filter accounts based on either the subscription price, lowest claimable promotional price, or regular price",
        default=None,
        required=False,
        type=click.Choice(["paid", "free"], case_sensitive=False),
        callback=lambda ctx, param, value: value.lower() if value else None,
    ),
    click.option(
        "-rp",
        "--renewal-price",
        help="Filter accounts based on either the lowest claimable promotional price, or regular price",
        default=None,
        required=False,
        type=click.Choice(["paid", "free"], case_sensitive=False),
        callback=lambda ctx, param, value: value.lower() if value else None,
    ),
    click.option(
        "-gp",
        "--regular-price",
        help="Filter accounts based on the regular price",
        default=None,
        required=False,
        type=click.Choice(["paid", "free"], case_sensitive=False),
        callback=lambda ctx, param, value: value.lower() if value else None,
    ),
    click.option(
        "-pp",
        "--promo-price",
        help="Filter accounts based on either the lowest promotional price regardless of claimability, or regular price",
        default=None,
        required=False,
        type=click.Choice(["paid", "free"], case_sensitive=False),
        callback=lambda ctx, param, value: value.lower() if value else None,
    ),
    click.constraints.mutually_exclusive(
        click.option(
            "-lo",
            "--last-seen-only",
            "last_seen",
            help="Filter accounts to ones where last seen is visible",
            default=None,
            required=False,
            is_flag=True,
        ),
        click.option(
            "-ls",
            "--last-seen-skip",
            "last_seen",
            help="Filter accounts to ones where last seen is hidden",
            default=False,
            required=False,
            is_flag=True,
        ),
    ),
    click.option(
        "-fo/-fs",
        "--free-trial-only/--free-trial-skip",
        "free_trail",  # Positional argument for destination attribute
        # help="Filter accounts to only those currently in a free trial (normally paid)",
        # default=None,
        required=False,
        is_flag=True,
        default=None,
    ),
    click.option(
        "-po/-ps",
        "--promo-only/--promo-skip",
        "promo",  # Change dest to be the third element in the list
        help="Filter accounts with any claimable promo price",
        default=None,
        required=False,
        is_flag=True,
        flag_value=True,
    ),
    click.option(
        "-ao",
        "--all-promo-only/--all-promo-skip",
        "all_promo",  # Keep the provided dest
        help="Filter accounts with any promo price",
        default=None,
        required=False,
        is_flag=True,
        flag_value=True,
    ),
    click.option(
        "-ts/-es",
        "--active-subscription/--expired-subscription",
        "sub_status",
        help="Filter accounts to those with non-expired status",
        default=None,
        required=False,
        is_flag=True,
        flag_value=True,
    ),
    click.option(
        "-ro/-rf",
        "--renew-on/--renew-off",
        "renewal",
        help="Filter accounts to those with the renew flag on",
        default=None,
        required=False,
        is_flag=True,
        flag_value=True,
    ),
    click.option(
        "-ul",
        "--user-list",
        help="Filter by userlist. Note: the lists 'ofscraper.main', 'ofscraper.expired', and 'ofscraper.active' are reserved and should not be the name of any list you have on OF",
        default=None,
        multiple=True,
        callback=lambda ctx, param, value: list(
            set(
                itertools.chain.from_iterable(
                    [
                        (
                            re.split(r"[,\s]+", item.lower())
                            if isinstance(item, str)
                            else item
                        )
                        for item in value
                    ]
                )
            )
        ),
    ),
    click.option(
        "-bl",
        "--black-list",
        help="Remove all users from selected list. Note: the lists 'ofscraper.main', 'ofscraper.expired', and 'ofscraper.active' are reserved and should not be the name of any list you have on OF",
        default=None,
        multiple=True,
        callback=lambda ctx, param, value: list(
            set(
                itertools.chain.from_iterable(
                    [
                        (
                            re.split(r"[,\s]+", item.lower())
                            if isinstance(item, str)
                            else item
                        )
                        for item in value
                    ]
                )
            )
        ),
    ),
    help="Filters out usernames based on selected parameters",
)
@click.option_group(
    "advanced filters",
    click.option(
        "-ppn",
        "--promo-price-min",
        help="Filter accounts where the lowest promo price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-ppm",
        "--promo-price-max",
        help="Filter accounts where the lowest promo price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-gpn",
        "--regular-price-min",
        help="Filter accounts where the regular price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-gpm",
        "--regular-price-max",
        help="Filter accounts where the regular price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-cpn",
        "--current-price-min",
        help="Filter accounts where the current regular price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-cpm",
        "--current-price-max",
        help="Filter accounts where the current price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-rpn",
        "--renewal-price-min",
        help="Filter accounts where the renewal regular price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-rpm",
        "--renewal-price-max",
        help="Filter accounts where the renewal price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    ),
    click.option(
        "-lsb",
        "--last-seen-before",
        help="Filter accounts by last seen being at or before the given date (YYYY-MM-DD format)",
        default=None,
        required=False,
        callback=lambda ctx, param, value: (
            helpers.arrow_helper(value) if value else None
        ),
    ),
    click.option(
        "-lsa",
        "--last-seen-after",
        help="Filter accounts by last seen being at or after the given date (YYYY-MM-DD format)",
        default=None,
        required=False,
        callback=lambda ctx, param, value: (
            helpers.arrow_helper(value) if value else None
        ),
    ),
    click.option(
        "-ea",
        "--expired-after",
        help="Filter accounts by expiration/renewal being at or after the given date (YYYY-MM-DD format)",
        default=None,
        required=False,
        callback=lambda ctx, param, value: (
            helpers.arrow_helper(value) if value else None
        ),
    ),
    click.option(
        "-eb",
        "--expired-before",
        help="Filter accounts by expiration/renewal being at or before the given date (YYYY-MM-DD format)",
        default=None,
        required=False,
        callback=lambda ctx, param, value: (
            helpers.arrow_helper(value) if value else None
        ),
    ),
    click.option(
        "-sa",
        "--subscribed-after",
        help="Filter accounts by subscription date being after the given date (YYYY-MM-DD format)",
        default=None,
        required=False,
        callback=lambda ctx, param, value: (
            helpers.arrow_helper(value) if value else None
        ),
    ),
    click.option(
        "-sb",
        "--subscribed-before",
        help="Filter accounts by sub date being at or before the given date (YYYY-MM-DD format)",
        default=None,
        required=False,
        callback=lambda ctx, param, value: (
            helpers.arrow_helper(value) if value else None
        ),
    ),
    help="Advanced filtering of accounts based on more precise user-defined parameters",
)
@click.option_group(
    "Model Sort",
    click.option(
        "-st",
        "--sort",
        help="What to sort the model list by",
        default="Name",
        type=click.Choice(
            [
                "name",
                "subscribed",
                "expired",
                "current-price",
                "renewal-price",
                "regular-price",
                "promo-price",
                "last-seen",
            ],
            case_sensitive=False,
        ),
        callback=lambda ctx, param, value: value.lower() if value else None,
    ),
    click.option(
        "-ds",
        "--desc",
        help="Sort the model list in descending order",
        is_flag=True,
        default=False,
    ),
    help="Controls the order of the model selection list and the scraping order",
)
@common_params
@click.pass_context
def program(ctx, *args, **kwargs):
    return ctx.params, ctx.invoked_subcommand


@program.command("post_check", help="produce a table of models posts")
@click.constraints.require_one(
    click.option(
        "-u",
        "--url",
        help="Scan posts via space or comma seperated list of urls",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
    click.option(
        "-f",
        "--file",
        help="Scan posts via a file with line-separated URL(s)",
        default=None,
        type=helpers.check_filehelper,
        multiple=True,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
)
@click.option(
    "-fo",
    "--force",
    help="Force retrieval of new posts info from API",
    is_flag=True,
    default=False,
)
@click.option(
    "-ca",
    "--check-area",
    help="Select areas to check (multiple allowed, separated by spaces)",
    default=["Timeline", "Pinned", "Archived"],
    type=click.Choice(
        ["Timeline", "Pinned", "Archived", "Labels"], case_sensitive=False
    ),
    callback=lambda ctx, param, value: (
        list(set(helpers.post_check_area(value))) if value else None
    ),
    multiple=True,
)
@common_params
@common_other_params
@click.pass_context
def post_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name


@program.command("msg_check", help="produce a table of models messages")
@click.constraints.require_one(
    click.option(
        "-u",
        "--url",
        help="Scan messages via space or comma seperated list of urls",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
    click.option(
        "-f",
        "--file",
        help="Scan messages via a file with line-separated URL(s)",
        default=None,
        type=helpers.check_filehelper,
        multiple=True,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),  # Open file for reading
    ),
)
@click.option(
    "-fo",
    "--force",
    help="Force retrieval of new messages info from API",
    is_flag=True,
    default=False,
)
@common_params
@common_other_params
@click.pass_context
def message_check(ctx, *args, **kwargs):
    return ctx.params, ctx.invoked_subcommand


@program.command("paid_check", help="produce a table of purchases from a model")
@click.constraints.require_one(
    click.option(
        "-u",
        "--username",
        help="Scan purchases via username(s)",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
    ),
    click.option(
        "-f",
        "--file",
        help="Scan pu via a file with line-separated URL(s)",
        default=None,
        type=helpers.check_filehelper,
        multiple=True,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
)
@click.option(
    "-fo",
    "--force",
    help="Force retrieval of new purchases info from API",
    is_flag=True,
    default=False,
)
@common_params
@common_other_params
@click.pass_context
def paid_check(ctx, *args, **kwargs):
    return ctx.params, ctx.invoked_subcommand


@program.command("story_check", help="produce a table of models stories/highlights")
@click.constraints.require_one(
    click.option(
        "-u",
        "--username",
        help="Scan stories/highlights via username(s)",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
    ),
    click.option(
        "-f",
        "--file",
        help="Scan stories/highlights via a file with line-separated URL(s)",
        default=None,
        type=helpers.check_filehelper,
        multiple=True,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
)
@click.option(
    "-fo",
    "--force",
    help="Force retrieval of new messages info from API",
    is_flag=True,
    default=False,
)
@common_params
@common_other_params
@click.pass_context
def story_check(ctx, *args, **kwargs):
    return ctx.params, ctx.invoked_subcommand


@program.command("manual", help="Manually download content via url or ID")
@click.constraints.require_one(
    click.option(
        "-u",
        "--url",
        help="A space or comma seperated list of urls to download",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
    ),
    click.option(
        "-f",
        "--file",
        help="file with line-separated URL(s) for downloading",
        default=None,
        type=helpers.check_filehelper,
        multiple=True,
        callback=lambda ctx, param, value: (
            list(set(itertools.chain.from_iterable(value))) if value else None
        ),
    ),
)
@click.option(
    "-fo",
    "--force",
    help="Force retrieval of new messages info from API",
    is_flag=True,
    default=False,
)
@common_params
@common_other_params
@click.pass_context
def manual(ctx, *args, **kwargs):
    return ctx.params, ctx.invoked_subcommand


def parse_args():
    try:
        result = program(standalone_mode=False)
        if result == 0:
            quit()
        args, command = result
        args["command"] = command
        d = AutoDotDict(args)
        import pprint

        pprint.pprint(d)
        quit()
        return d
    except SystemExit as e:
        if e.code != 0:
            raise


# def parse_args(input=None):
#     parser = create_parser(input)

#     args = parser.parse_args(input)

#     # fix args
#     args.username = set(args.username or [])
#     args.excluded_username = set(args.excluded_username or [])
#     args.label = set(args.label) if args.label else args.label
#     if args.command in set(["post_check", "msg_check"]) and not (args.url or args.file):
#         raise argparse.ArgumentTypeError(
#             "error: argument missing --url or --file must be specified )"
#         )
#     elif args.command in set(["story_check", "paid_check"]) and not (
#         args.username or args.file
#     ):
#         raise argparse.ArgumentTypeError(
#             "error: argument missing --username or --file must be specified )"
#         )
#     elif args.command in set(["manual"]) and not (args.url or args.file):
#         raise argparse.ArgumentTypeError(
#             "error: argument missing --url or --file must be specified )"
#         )
#     write_args.setArgs(args)
#     return args
