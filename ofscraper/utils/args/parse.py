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
            return self[attr]
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
        help="global options for all commands"

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
        ),
        help="Settigns for logging"

    )
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx,*args, **kwargs):
        return func(ctx,*args, **kwargs)
    return wrapper







@click.group(
    help="Program Args",
    context_settings=dict(help_option_names=["-h", "--help"]),
    invoke_without_command=True
)
@click.option_group(
    "scraper",
    click.option(
        "-u",
        "--usernames",
        help="Select which username to process (name,name2). Set to ALL for all users.",
        type=helpers.username_helper,  # Assuming you'll still use this helper function
        multiple=True,  # Use `multiple=True` for accepting multiple values
    ),
    click.option(
        "-eu",
        "--excluded-username",
        help="Select which usernames to exclude (name,name2). Has preference over --username.",
        type=helpers.username_helper,
        multiple=True,
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
        type=click.Choice(["like", "unlike", "download"]),  # Enforce valid choices
        multiple=True,
    ),
    help="basic options for actions"
)
@click.option_group(
    "user filters",
    click.option(
        "-cp",
        "--current-price",
        help="Filter accounts based on either the subscription price, lowest claimable promotional price, or regular price",
        default=None,
        required=False,
                type=click.Choice(["paid", "free"]),
    ),
    click.option(
        "-rp",
        "--renewal-price",
        help="Filter accounts based on either the lowest claimable promotional price, or regular price",
        default=None,
        required=False,
                type=click.Choice(["paid", "free"]),
    ),
    click.option(
        "-gp",
        "--regular-price",
        help="Filter accounts based on the regular price",
        default=None,
        required=False,
                type=click.Choice(["paid", "free"]),
    ),
    click.option(
        "-pp",
        "--promo-price",
        help="Filter accounts based on either the lowest promotional price regardless of claimability, or regular price",
        default=None,
        required=False,
                type=click.Choice(["paid", "free"]),
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
            "-fo",
            "--free-trial-only/--free-trial-skip",
            "free_trail",  # Positional argument for destination attribute
            # help="Filter accounts to only those currently in a free trial (normally paid)",
            # default=None,
            required=False,
            is_flag=True,
            default=None
        ),


                click.option(
                    "-po",
                    "--promo-only/--promo-skip",
                    "promo",  # Change dest to be the third element in the list
                    help="Filter accounts with any claimable promo price",
                    default=None,
                    required=False,
                              is_flag=True,
                            flag_value=True            ),

                click.option(
                    "-ao",
                    "--all-promo-only/--all-promo-skip",
                    "all_promo",  # Keep the provided dest
                    help="Filter accounts with any promo price",
                    default=None,
                    required=False,
                              is_flag=True,
                            flag_value=True           ),
        click.option(
            "-ts",
            "--active-subscription/--expired-subscription",
            "sub_status",
            help="Filter accounts to those with non-expired status",
            default=None,
            required=False,
                              is_flag=True,
                            flag_value=True
        ),
        click.option(
            "-ro",
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
    default=[],
    callback=lambda ctx, param, value: list(set(itertools.chain.from_iterable([
    re.split(r"[,\s]+",item.lower()) if isinstance(item, str) else item
    for item in value
]))),
),
click.option(
    "-bl",
    "--black-list",
    help="Remove all users from selected list. Note: the lists 'ofscraper.main', 'ofscraper.expired', and 'ofscraper.active' are reserved and should not be the name of any list you have on OF",
    default=None,
    multiple=True,
    callback=lambda ctx, param, value: list(set(itertools.chain.from_iterable([
    re.split(r"[,\s]+",item.lower()) if isinstance(item, str) else item
    for item in value
]))),
),
help="Filters out usernames based on selected parameters"
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
    callback=lambda ctx, param, value: helpers.arrow_helper(value)  if value else None,
),
click.option(
    "-lsa",
    "--last-seen-after",
    help="Filter accounts by last seen being at or after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: helpers.arrow_helper(value)  if value else None,
),
click.option(
    "-ea",
    "--expired-after",
    help="Filter accounts by expiration/renewal being at or after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: helpers.arrow_helper(value) if value else None,
),
click.option(
    "-eb",
    "--expired-before",
    help="Filter accounts by expiration/renewal being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: helpers.arrow_helper(value)  if value else None,
),
click.option(
    "-sa",
    "--subscribed-after",
    help="Filter accounts by subscription date being after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: helpers.arrow_helper(value)  if value else None
),
click.option(
    "-sb",
    "--subscribed-before",
    help="Filter accounts by sub date being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: helpers.arrow_helper(value) if value else None
),
help="Advanced filtering of accounts based on more precise user-defined parameters"

)
@common_params
@click.pass_context
def program(ctx,*args,**kwargs):
    return ctx.params



@program.command("post_check",help="produce a table of models posts")
@click.option(
    "-u",
    "--url",
    help="Scan posts via url. You can provide multiple URLs separated by spaces.",
    default=None,
    multiple=True,
    type=helpers.check_strhelper,
)
@click.option(
    "-f",
    "--file",
    help="Scan posts via file\nWith line-separated URL(s)",
    default=None,
    type=helpers.check_filehelper,  # Open file for reading
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
    type=click.Choice(["Timeline", "Pinned", "Archived"]),
    multiple=True,
)
@common_params
@click.pass_context
def post_check(ctx, *args,**kwargs):
    return ctx.params
def parse_args():
    try:
        args = program(standalone_mode=False)
        if args==0:
            quit()
        d = AutoDotDict(args)
        import pprint
        pprint.pprint(d)

        quit()
    except SystemExit as e:
        if e.code != 0:
            raise



# def create_parser(input=None):
#     post = parser.add_argument_group("Post", description="What type of post to scrape")

#     post.add_argument(
#         "-q",
#         "--quality",
#         default="source",
#         help="Set the minimum allowed quality for videos",
#         choices=["240", "720", "source"],
#     )

#     post.add_argument(
#         "-o",
#         "--posts",
#         help="""
# Select area(s) for batch action(s)
# Select from [HighLights,Archived,Messages,Timeline,Pinned,Stories,Purchased,Profile,Labels] or All
# Accepts space or comma seperated list
# """,
#         default=[],
#         required=False,
#         type=helpers.posttype_helper,
#         action="extend",
#     )

#     post.add_argument(
#         "-da",
#         "--download-area",
#         help="""
# Perform download action in specified area(s)
# Select from [HighLights,Archived,Messages,Timeline,Pinned,Stories,Purchased,Profile,Labels] or All
# Has preference over --posts
# Accepts space or comma seperated list
# """,
#         default=[],
#         required=False,
#         type=helpers.download_helper,
#         action="extend",
#     )

#     post.add_argument(
#         "-la",
#         "--like-area",
#         help="""
# Perform like/unlike action in selected area(s)
# [Archived,Timeline,Pinned,Labels] or All
# Has preference over --posts
# Accepts space or comma seperated list
# """,
#         default=[],
#         required=False,
#         type=helpers.like_helper,
#         action="extend",
#     )

#     post.add_argument(
#         "-ft",
#         "--filter",
#         help="Filter post to where the provided regex True\nNote if you include any uppercase characters the search will be case-sensitive",
#         default=".*",
#         required=False,
#         type=str,
#     )

#     post.add_argument(
#         "-nf",
#         "--neg-filter",
#         help="Filter post by provide regex is False\nNote if you include any uppercase characters the search will be case-sensitive",
#         default=None,
#         required=False,
#         type=str,
#     )
#     post.add_argument(
#         "-sp",
#         "--scrape-paid",
#         help="scrape the entire paid page for content. This can take a very long time the first time",
#         default=None,
#         required=False,
#         action="store_true",
#     )
#     post.add_argument(
#         "-xc",
#         "--max-count",
#         help="Max number of post to download for a specific model starting from the oldest non-duped",
#         default=0,
#         required=False,
#         type=int,
#     )

#     post.add_argument(
#         "-it",
#         "--item-sort",
#         help="Change the order of items/posts before executing action. Default is by date asc or random depending on which downloader is used",
#         default=None,
#         required=False,
#         type=str,
#         choices=[
#             "random",
#             "text-asc",
#             "text-desc",
#             "date-asc",
#             "date-desc",
#             "filename-asc",
#             "filename-desc",
#         ],
#     )
#     groupf = post.add_mutually_exclusive_group()
#     groupf.add_argument(
#         "-e",
#         "--force-all",
#         action="store_true",
#         default=False,
#         help="Downloads all files regardless of whether it is in the database",
#     )
#     groupf.add_argument(
#         "-eq",
#         "--force-model-unique",
#         action="store_true",
#         default=False,
#         help="Only download if the file is not present for the current model in the database",
#     )

#     group10 = post.add_mutually_exclusive_group()
#     group10.add_argument(
#         "-to",
#         "--protected-only",
#         help="Only download  content that requires decryption",
#         default=False,
#         required=False,
#         action="store_true",
#     )
#     group10.add_argument(
#         "-no",
#         "--normal-only",
#         help="Only download content that does not require decryption",
#         default=False,
#         required=False,
#         action="store_true",
#     )

#     post.add_argument(
#         "-lb",
#         "--label",
#         help="Filter by label",
#         default=None,
#         required=False,
#         type=helpers.label_helper,
#         action="extend",
#     )
#     post.add_argument(
#         "-be",
#         "--before",
#         help="Process post at or before the given date general synax is Month/Day/Year\nWorks for like,unlike, and downloading posts",
#         type=helpers.arrow_helper,
#     )
#     post.add_argument(
#         "-af",
#         "--after",
#         help="Process post at or after the given date Month/Day/Year\nnWorks for like,unlike, and downloading posts",
#         type=helpers.arrow_helper,
#     )
#     post.add_argument(
#         "-mt",
#         "--mediatype",
#         help="Filter by media in the following areas [Videos,Audios,Images]",
#         default=[],
#         required=False,
#         type=helpers.mediatype_helper,
#         action="extend",
#     )
#     post.add_argument(
#         "-sx",
#         "--size-max",
#         help="Filter out files greater then given size supported inputs include int in bytes or human-readable such as 10mb",
#         required=False,
#         type=parse_size,
#     )
#     post.add_argument(
#         "-sm",
#         "--size-min",
#         help="Filter out files greater smaller then the given size bytes or human-readable such as 10mb",
#         required=False,
#         type=parse_size,
#     )

#     # mutual exclusive groups
#     group1 = post.add_mutually_exclusive_group()

#     group1.add_argument(
#         "-mm",
#         "--mass-only",
#         help="download mass messages only",
#         default=None,
#         required=False,
#         action="store_const",
#         dest="mass_msg",
#         const=True,
#     )

#     group1.add_argument(
#         "-ms",
#         "--mass-skip",
#         help="skip mass messages",
#         default=None,
#         required=False,
#         action="store_const",
#         dest="mass_msg",
#         const=False,
#     )
#     group2 = post.add_mutually_exclusive_group()
#     group2.add_argument(
#         "-sk",
#         "--skip-timed",
#         default=None,
#         help="skip promotional or temporary post",
#         action="store_const",
#         const=False,
#         dest="timed_only",
#     )
#     group2.add_argument(
#         "-ok",
#         "--only-timed",
#         default=None,
#         help="skip promotional or temporary post",
#         action="store_const",
#         const=True,
#         dest="timed_only",
#     )






#     adv_filters = parser.add_argument_group(
#         "Advanced model filters",
#         description="Advanced filtering of accounts based on more precise user-defined parameters",
#     )

#     adv_filters.add_argument(
#         "-ppn",
#         "--promo-price-min",
#         help="Filter accounts to those where the lowest promo price matches or falls above the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-ppm",
#         "--promo-price-max",
#         help="Filter accounts where the lowest promo price matches or falls below the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-gpn",
#         "--regular-price-min",
#         help="Filter accounts where the regular price matches or falls above the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-gpm",
#         "--regular-price-max",
#         help="Filter accounts where the regular price matches or falls below the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-cpn",
#         "--current-price-min",
#         help="Filter accounts where the current regular price matches or falls above the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-cpm",
#         "--current-price-max",
#         help="Filter accounts where the current price matches or falls below the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-rpn",
#         "--renewal-price-min",
#         help="Filter accounts where the renewal regular price matches or falls above the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-rpm",
#         "--renewal-price-max",
#         help="Filter accounts where the renewal price matches or falls below the provided value",
#         default=None,
#         required=False,
#         type=int,
#     )

#     adv_filters.add_argument(
#         "-lsb",
#         "--last-seen-before",
#         help="Filter accounts by last seen being at or before the given date",
#         default=None,
#         required=False,
#         type=helpers.arrow_helper,
#     )
#     adv_filters.add_argument(
#         "-lsa",
#         "--last-seen-after",
#         help="Filter accounts by last seen being at or after the given date",
#         default=None,
#         required=False,
#         type=helpers.arrow_helper,
#     )

#     adv_filters.add_argument(
#         "-ea",
#         "--expired-after",
#         help="Filter accounts by expiration/renewal being at or after the given date",
#         default=None,
#         required=False,
#         type=helpers.arrow_helper,
#     )
#     adv_filters.add_argument(
#         "-eb",
#         "--expired-before",
#         help="Filter accounts by expiration/renewal being at or before the given date",
#         default=None,
#         required=False,
#         type=helpers.arrow_helper,
#     )
#     adv_filters.add_argument(
#         "-sa",
#         "--subscribed-after",
#         help="Filter accounts by subscription date being after  the given date",
#         default=None,
#         required=False,
#         type=helpers.arrow_helper,
#     )
#     adv_filters.add_argument(
#         "-sb",
#         "--subscribed-before",
#         help="Filter accounts by sub date being at or before the given date",
#         default=None,
#         required=False,
#         type=helpers.arrow_helper,
#     )

#     sort = parser.add_argument_group(
#         "Model sort",
#         description="Controls the order of the model selection list and the scraping order",
#     )
#     sort.add_argument(
#         "-st",
#         "--sort",
#         help="What to sort the model list by",
#         default="Name",
#         choices=[
#             "name",
#             "subscribed",
#             "expired",
#             "current-price",
#             "renewal-price",
#             "regular-price",
#             "promo-price",
#             "last-seen",
#         ],
#         type=str.lower,
#     )
#     sort.add_argument(
#         "-ds",
#         "--desc",
#         help="Sort the model list in descending order",
#         action="store_true",
#         default=False,
#     )

#     advanced = parser.add_argument_group("Advanced", description="Advanced Args")
#     advanced.add_argument(
#         "-uf",
#         "--users-first",
#         help="Scrape all users first rather then one at a time. This only effects downloading posts",
#         default=False,
#         required=False,
#         action="store_true",
#     )
#     advanced.add_argument(
#         "-nc",
#         "--no-cache",
#         help="disable cache",
#         default=False,
#         required=False,
#         action="store_true",
#     )
#     advanced.add_argument(
#         "-k",
#         "--key-mode",
#         help="key mode override",
#         default=None,
#         required=False,
#         choices=KEY_OPTIONS,
#         type=str.lower,
#     )
#     advanced.add_argument(
#         "-dr",
#         "--dynamic-rules",
#         help="Dynamic signing",
#         default=None,
#         required=False,
#         choices=["dc", "deviint"],
#         type=str.lower,
#     )
#     advanced.add_argument(
#         "-ar",
#         "--no-auto-resume",
#         help="Cleanup temp .part files\nNote this removes the ability to resume from downloads",
#         default=False,
#         action="store_true",
#     )

#     advanced.add_argument(
#         "-db",
#         "--downloadbars",
#         help="show individual download progress bars",
#         default=False,
#         action="store_true",
#     )

#     advanced.add_argument(
#         "-sd",
#         "--downloadsems",
#         help="Number of sems or concurrent downloads per thread",
#         default=None,
#         type=int,
#     )

#     advanced.add_argument(
#         "-dp",
#         "--downloadthreads",
#         help="Number threads to use minimum will always be 1, total used never be higher then (total threads) -1",
#         default=None,
#         type=int,
#     )

#     advanced.add_argument(
#         "-up",
#         "--update-profile",
#         help="get up to date profile info instead of using cache",
#         default=False,
#         action="store_true",
#     )
#     group11 = advanced.add_mutually_exclusive_group()

#     group11.add_argument(
#         "-fi",
#         "--individual",
#         help="When --username arg is provided searches each username as a seperate request",
#         default=False,
#         action="store_true",
#     )

#     group11.add_argument(
#         "-fl",
#         "--list",
#         help="When --username arg is provided searches entire enabled list(s) before filtering for usernames",
#         default=False,
#         action="store_true",
#     )

#     group12 = advanced.add_mutually_exclusive_group()
#     group12.add_argument(
#         "-md",
#         "--metadata",
#         help="Skip all media downloads and gathers metadata only\nNo change to download status in media table",
#         default=None,
#         action="store_const",
#         dest="metadata",
#         const="none",
#     )
#     group12.add_argument(
#         "-mu",
#         "--metadata-update",
#         help="Skip all media downloads and gathers metadata only\nUpdates downloaded status in media table based on file presence",
#         default=None,
#         action="store_const",
#         dest="metadata",
#         const="file",
#     )
#     group12.add_argument(
#         "-mc",
#         "--metadata-complete",
#         help="Skip all media downloads and gathers metadata only\nMarks each media item as downloaded in media table",
#         default=None,
#         action="store_const",
#         dest="metadata",
#         const="complete",
#     )

#     subparser = parser.add_subparsers(help="commands", dest="command")
#     post_check = subparser.add_parser(
#         "post_check",
#         help="Generate a table of key information from model-extracted posts\nCache lasts for 24 hours",
#         parents=[global_parser],
#     )
#     post_check.add_argument(
#         "-u",
#         "--url",
#         help="Scan posts via url",
#         default=None,
#         required=False,
#         type=helpers.check_strhelper,
#         action="extend",
#     )

#     post_check.add_argument(
#         "-f",
#         "--file",
#         help="Scan posts via file\nWith line seperated URL(s)",
#         default=None,
#         required=False,
#         type=helpers.check_filehelper,
#     )

#     post_check.add_argument(
#         "-fo",
#         "--force",
#         help="force retrieval of new posts info from API",
#         default=False,
#         action="store_true",
#     )

#     post_check.add_argument(
#         "-ca",
#         "--check-area",
#         help="which areas to check",
#         default=["Timeline","Pinned","Archived"],
#         type=helpers.post_check_area
#     )

#     message_check = subparser.add_parser(
#         "msg_check",
#         help="Generate a table of key information from model-extracted messages\nCache lasts for 24 hours",
#         parents=[parent_parser],
#     )
#     message_check.add_argument(
#         "-fo",
#         "--force",
#         help="force retrieval of new messages info from API",
#         default=False,
#         action="store_true",
#     )
#     message_check.add_argument(
#         "-f",
#         "--file",
#         help="Scan messages via file\nWith line seperated URL(s)",
#         default=None,
#         required=False,
#         type=helpers.check_filehelper,
#     )

#     message_check.add_argument(
#         "-u",
#         "--url",
#         help="scan messages via file",
#         type=helpers.check_strhelper,
#         action="extend",
#     )

#     paid_check = subparser.add_parser(
#         "paid_check",
#         help="Generate a table of key information from model-extracted purchases\nCache last for 24 hours",
#         parents=[parent_parser],
#     )
#     paid_check.add_argument(
#         "-fo",
#         "--force",
#         help="force retrieval of new purchases info from API",
#         default=False,
#         action="store_true",
#     )
#     paid_check.add_argument(
#         "-f",
#         "--file",
#         help="Scan purchases via file\nWith line seperated usernames(s)",
#         default=None,
#         required=False,
#         type=helpers.check_filehelper,
#     )

#     paid_check.add_argument(
#         "-u",
#         "--username",
#         help="Scan purchases via usernames",
#         type=helpers.check_strhelper,
#         action="extend",
#     )

#     story_check = subparser.add_parser(
#         "story_check",
#         help="Generate a table of key information from model-extracted story/highlights\nCache last for 24 hours",
#         parents=[parent_parser],
#     )
#     story_check.add_argument(
#         "-fo",
#         "--force",
#         help="force retrieval of new posts info from API",
#         default=False,
#         action="store_true",
#     )
#     story_check.add_argument(
#         "-f",
#         "--file",
#         help="Scan mevia file",
#         default=None,
#         required=False,
#         type=helpers.check_filehelper,
#     )

#     story_check.add_argument(
#         "-u",
#         "--username",
#         help="link to conversation",
#         type=helpers.check_strhelper,
#         action="extend",
#     )

#     manual = subparser.add_parser(
#         "manual",
#         help="Manually download content via url or ID",
#         parents=[parent_parser],
#     )
#     manual.add_argument(
#         "-f",
#         "--file",
#         help="Pass links/IDs to download via file",
#         default=None,
#         required=False,
#         type=helpers.check_filehelper,
#     )
#     manual.add_argument(
#         "-u",
#         "--url",
#         help="pass links to download via url",
#         type=helpers.check_strhelper,
#         action="extend",
#     )

#     return parser


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
