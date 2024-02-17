import argparse
import re
import sys

from humanfriendly import parse_size

import ofscraper.utils.args.helpers as helpers
import ofscraper.utils.args.write as write_args
import ofscraper.utils.system.system as system
from ofscraper.__version__ import __version__
from ofscraper.const.constants import KEY_OPTIONS


def create_parser(input=None):
    if "pytest" in sys.modules and input == None:
        input = []
    elif input == None:
        input = sys.argv[1:]
    if not system.get_parent():
        input = []
    parent_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=True)
    general = parent_parser.add_argument_group("Program", description="Program Args")
    general.add_argument(
        "-v", "--version", action="version", version=__version__, default=__version__
    )
    general.add_argument(
        "-cg", "--config", help="Change location of config folder/file", default=None
    )
    general.add_argument(
        "-r",
        "--profile",
        help="Change which profile you want to use\nIf not set then the config file is used\nProfiles are always within the config file parent directory",
        default=None,
        type=lambda x: f"{re.sub('_profile','', x)}_profile",
    )
    output = parent_parser.add_argument_group(
        "Logging", description="Arguments for output controls"
    )

    output.add_argument(
        "-l",
        "--log",
        help="set log file level",
        type=str.upper,
        default="OFF",
        choices=["OFF", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
    ),
    output.add_argument(
        "-dc",
        "--discord",
        help="set discord log level",
        type=str.upper,
        default="OFF",
        choices=["OFF", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
    )

    output.add_argument(
        "-p",
        "--output",
        help="set console output log level",
        type=str.upper,
        default="NORMAL",
        choices=["PROMPT", "STATS", "LOW", "NORMAL", "DEBUG", "TRACE"],
    )

    parser = argparse.ArgumentParser(
        add_help=False, parents=[parent_parser], prog="OF-Scraper"
    )
    parser.add_argument("-h", "--help", action="help")
    scraper = parser.add_argument_group(
        "scraper", description="General Arguments for scraper"
    )
    scraper.add_argument(
        "-u",
        "--username",
        help="select which username to process (name,name2)\nSet to ALL for all users",
        type=helpers.username_helper,
        action="extend",
    )
    scraper.add_argument(
        "-eu",
        "--excluded-username",
        help="select which usernames to exclude  (name,name2)\nThis has preference over --username",
        type=helpers.username_helper,
        action="extend",
    )

    scraper.add_argument(
        "-d",
        "--daemon",
        help="run script in the background\nSet value to minimum minutes between script runs\nOverdue runs will run as soon as previous run finishes",
        type=float,
        default=None,
    )

    scraper.add_argument(
        "-g",
        "--original",
        help="don't truncate long paths",
        default=None,
        action="store_true",
    )
    scraper.add_argument(
        "-a",
        "--action",
        help="perform batch action on users",
        default=[],
        required=False,
        type=helpers.action_helper,
        action="extend",
    )

    post = parser.add_argument_group("Post", description="What type of post to scrape")

    post.add_argument(
        "-e",
        "--dupe",
        action="store_true",
        default=False,
        help="Bypass the dupe check and redownload all files",
    )

    post.add_argument(
        "-q",
        "--quality",
        default="source",
        help="Set the minimum allowed quality for videos",
        choices=["240", "720", "source"],
    )

    post.add_argument(
        "-o",
        "--posts",
        help="Perform action in following areas",
        default=[],
        required=False,
        type=helpers.posttype_helper,
        action="extend",
    )

    post.add_argument(
        "-da",
        "--download-area",
        help="Download specified content from a model",
        default=[],
        required=False,
        type=helpers.download_helper,
        action="extend",
    )

    post.add_argument(
        "-la",
        "--like-area",
        help="Batch unlike or likes in specific aera",
        default=[],
        required=False,
        type=helpers.like_helper,
        action="extend",
    )

    post.add_argument(
        "-ft",
        "--filter",
        help="Filter post to where the provided regex True\nNote if you include any uppercase characters the search will be case-sensitive",
        default=".*",
        required=False,
        type=str,
    )

    post.add_argument(
        "-nf",
        "--neg-filter",
        help="Filter post by provide regex is False\nNote if you include any uppercase characters the search will be case-sensitive",
        default=None,
        required=False,
        type=str,
    )
    post.add_argument(
        "-sp",
        "--scrape-paid",
        help="scrape the entire paid page for content. This can take a very long time the first time",
        default=None,
        required=False,
        action="store_true",
    )
    post.add_argument(
        "-xc",
        "--max-count",
        help="Max number of post to download for a specific model starting from the oldest non-duped",
        default=0,
        required=False,
        type=int,
    )

    post.add_argument(
        "-it",
        "--item-sort",
        help="Change the order of items/posts before executing action. Default is by date asc or random depending on which downloader is used",
        default=None,
        required=False,
        type=str,
        choices=[
            "random",
            "text-asc",
            "text-desc",
            "date-asc",
            "date-desc",
            "filename-asc",
            "filename-desc",
        ],
    )

    group10 = post.add_mutually_exclusive_group()
    group10.add_argument(
        "-to",
        "--protected-only",
        help="Only download  content that requires decryption",
        default=False,
        required=False,
        action="store_true",
    )
    group10.add_argument(
        "-no",
        "--normal-only",
        help="Only download content that does not require decryption",
        default=False,
        required=False,
        action="store_true",
    )

    post.add_argument(
        "-lb",
        "--label",
        help="Filter by label",
        default=None,
        required=False,
        type=helpers.label_helper,
        action="extend",
    )
    post.add_argument(
        "-be",
        "--before",
        help="Process post at or before the given date general synax is Month/Day/Year\nWorks for like,unlike, and downloading posts",
        type=helpers.arrow_helper,
    )
    post.add_argument(
        "-af",
        "--after",
        help="Process post at or after the given date Month/Day/Year\nnWorks for like,unlike, and downloading posts",
        type=helpers.arrow_helper,
    )
    post.add_argument(
        "-mt",
        "--mediatype",
        help="Filter by media",
        default=[],
        required=False,
        type=helpers.mediatype_helper,
        action="extend",
    )
    post.add_argument(
        "-sx",
        "--size-max",
        help="Filter out files greater then given size supported inputs include int in bytes or human-readable such as 10mb",
        required=False,
        type=parse_size,
    )
    post.add_argument(
        "-sm",
        "--size-min",
        help="Filter out files greater smaller then the given size bytes or human-readable such as 10mb",
        required=False,
        type=parse_size,
    )

    # mutual exclusive groups
    group1 = post.add_mutually_exclusive_group()

    group1.add_argument(
        "-mm",
        "--mass-only",
        help="download mass messages only",
        default=None,
        required=False,
        action="store_const",
        dest="mass_msg",
        const=True,
    )

    group1.add_argument(
        "-ms",
        "--mass-skip",
        help="skip mass messages",
        default=None,
        required=False,
        action="store_const",
        dest="mass_msg",
        const=False,
    )
    group2 = post.add_mutually_exclusive_group()
    group2.add_argument(
        "-sk",
        "--skip-timed",
        default=None,
        help="skip promotional or temporary post",
        action="store_const",
        const=False,
        dest="timed_only",
    )
    group2.add_argument(
        "-ok",
        "--only-timed",
        default=None,
        help="skip promotional or temporary post",
        action="store_const",
        const=True,
        dest="timed_only",
    )

    # Filters for accounts
    filters = parser.add_argument_group(
        "Model filters",
        description="Filters out usernames based on selected parameters",
    )

    filters.add_argument(
        "-cp",
        "--current-price",
        help="Filter accounts based on either the subscription price, claimable promotions, or regular price",
        default=None,
        required=False,
        type=str.lower,
        choices=["paid", "free"],
    )

    filters.add_argument(
        "-rp",
        "--renewal-price",
        help="Filter accounts based on either the subscription price, claimable promotions, or regular price",
        default=None,
        required=False,
        type=str.lower,
        choices=["paid", "free"],
    )

    filters.add_argument(
        "-gp",
        "--regular-price",
        help="Filter accounts based on the regular price",
        default=None,
        required=False,
        type=str.lower,
        choices=["paid", "free"],
    )

    filters.add_argument(
        "-pp",
        "--promo-price",
        help="Filter accounts based on either the all promos included unclaimable, or regular price",
        default=None,
        required=False,
        type=str.lower,
        choices=["paid", "free"],
    )

    group3 = filters.add_mutually_exclusive_group()
    group3.add_argument(
        "-lo",
        "--last-seen-only",
        help="Filter accounts to ones where last seen is visible",
        default=None,
        required=False,
        const=True,
        dest="last_seen",
        action="store_const",
    )
    group3.add_argument(
        "-ls",
        "--last-seen-skip",
        help="Filter accounts to ones where last seen is hidden",
        default=None,
        required=False,
        const=False,
        dest="last_seen",
        action="store_const",
    )

    group4 = filters.add_mutually_exclusive_group()
    group4.add_argument(
        "-fo",
        "--free-trial-only",
        help="Filter accounts to only those currently in a free trial (normally paid)",
        default=None,
        required=False,
        const=True,
        dest="free_trial",
        action="store_const",
    )
    group4.add_argument(
        "-fs",
        "--free-trial-skip",
        help="Filter accounts to only those currently not in  a free trial (normally paid)",
        default=None,
        required=False,
        const=False,
        dest="free_trial",
        action="store_const",
    )

    group5 = filters.add_mutually_exclusive_group()
    group5.add_argument(
        "-po",
        "-promo-only",
        help="Filter accounts to ones with any claimable promo price",
        default=None,
        required=False,
        const=True,
        dest="promo",
        action="store_const",
    )
    group5.add_argument(
        "-ps",
        "--promo-skip",
        help="Filter accounts to ones without any claimable promo price",
        default=None,
        required=False,
        const=False,
        dest="promo",
        action="store_const",
    )

    group6 = filters.add_mutually_exclusive_group()
    group6.add_argument(
        "-ao",
        "--all-promo-only",
        help="Filter accounts to ones with any promo price",
        default=None,
        required=False,
        const=True,
        dest="all_promo",
        action="store_const",
    )
    group6.add_argument(
        "-as",
        "--all-promo-skip",
        help="Filter accounts to ones without any promo price",
        default=None,
        required=False,
        const=False,
        dest="all_promo",
        action="store_const",
    )

    group7 = filters.add_mutually_exclusive_group()
    group7.add_argument(
        "-ts",
        "--active-subscription",
        help="Filter accounts to those with non-expired status",
        default=None,
        required=False,
        const=True,
        dest="sub_status",
        action="store_const",
    )
    group7.add_argument(
        "-es",
        "--expired-subscription",
        help="Filter accounts to those with expired status",
        default=None,
        required=False,
        const=False,
        dest="sub_status",
        action="store_const",
    )

    group8 = filters.add_mutually_exclusive_group()
    group8.add_argument(
        "-ro",
        "--renew-on",
        help="Filter accounts to those with the renew flag on",
        default=None,
        required=False,
        const=True,
        dest="renewal",
        action="store_const",
    )
    group8.add_argument(
        "-rf",
        "--renew-off",
        help="Filter accounts to those with the renew flag off",
        default=None,
        required=False,
        const=False,
        dest="renewal",
        action="store_const",
    )

    filters.add_argument(
        "-ul",
        "--user-list",
        help='Filter by userlist\n Note:  the lists "ofscraper.main,ofscraper.expired,ofscraper.active" are reserved  and should not be the name of any list you have on OF',
        default=[],
        required=False,
        type=lambda x: list(map(lambda x: x.lower(), x.split(","))),
        action="extend",
    )

    filters.add_argument(
        "-bl",
        "--black-list",
        help='Remove all users from selected list\n Note: the lists "ofscraper.main,ofscraper.expired,ofscraper.active" are reserved should not be the name of any list you have on OF',
        default=[],
        required=False,
        type=lambda x: list(map(lambda x: x.lower(), x.split(","))),
        action="extend",
    )

    adv_filters = parser.add_argument_group(
        "Advanced model filters",
        description="Advanced filtering of accounts based on more precise user-defined parameters",
    )

    adv_filters.add_argument(
        "-ppn",
        "--promo-price-min",
        help="Filter accounts to those where the lowest promo price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-ppm",
        "--promo-price-max",
        help="Filter accounts where the lowest promo price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-gpn",
        "--regular-price-min",
        help="Filter accounts where the regular price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-gpm",
        "--regular-price-max",
        help="Filter accounts where the regular price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-cpn",
        "--current-price-min",
        help="Filter accounts where the current regular price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-cpm",
        "--current-price-max",
        help="Filter accounts where the current price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-rpn",
        "--renewal-price-min",
        help="Filter accounts where the renewal regular price matches or falls above the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-rpm",
        "--renewal-price-max",
        help="Filter accounts where the renewal price matches or falls below the provided value",
        default=None,
        required=False,
        type=int,
    )

    adv_filters.add_argument(
        "-lsb",
        "--last-seen-before",
        help="Filter accounts by last seen being at or before the given date",
        default=None,
        required=False,
        type=helpers.arrow_helper,
    )
    adv_filters.add_argument(
        "-lsa",
        "--last-seen-after",
        help="Filter accounts by last seen being at or after the given date",
        default=None,
        required=False,
        type=helpers.arrow_helper,
    )

    adv_filters.add_argument(
        "-ea",
        "--expired-after",
        help="Filter accounts by expiration/renewal being at or after the given date",
        default=None,
        required=False,
        type=helpers.arrow_helper,
    )
    adv_filters.add_argument(
        "-eb",
        "--expired-before",
        help="Filter accounts by expiration/renewal being at or before the given date",
        default=None,
        required=False,
        type=helpers.arrow_helper,
    )
    adv_filters.add_argument(
        "-sa",
        "--subscribed-after",
        help="Filter accounts by subscription date being after  the given date",
        default=None,
        required=False,
        type=helpers.arrow_helper,
    )
    adv_filters.add_argument(
        "-sb",
        "--subscribed-before",
        help="Filter accounts by sub date being at or before the given date",
        default=None,
        required=False,
        type=helpers.arrow_helper,
    )

    sort = parser.add_argument_group(
        "Model sort",
        description="Controls the order of the model selection list and the scraping order",
    )
    sort.add_argument(
        "-st",
        "--sort",
        help="What to sort the model list by",
        default="Name",
        choices=[
            "name",
            "subscribed",
            "expired",
            "current-price",
            "renewal-price",
            "regular-price",
            "promo-price",
            "last-seen",
        ],
        type=str.lower,
    )
    sort.add_argument(
        "-ds",
        "--desc",
        help="Sort the model list in descending order",
        action="store_true",
        default=False,
    )

    advanced = parser.add_argument_group("Advanced", description="Advanced Args")
    advanced.add_argument(
        "-uf",
        "--users-first",
        help="Scrape all users first rather then one at a time. This only effects downloading posts",
        default=False,
        required=False,
        action="store_true",
    )
    advanced.add_argument(
        "-nc",
        "--no-cache",
        help="disable cache",
        default=False,
        required=False,
        action="store_true",
    )
    advanced.add_argument(
        "-k",
        "--key-mode",
        help="key mode override",
        default=None,
        required=False,
        choices=KEY_OPTIONS,
        type=str.lower,
    )
    advanced.add_argument(
        "-dr",
        "--dynamic-rules",
        help="Dynamic signing",
        default=None,
        required=False,
        choices=["dc", "deviint"],
        type=str.lower,
    )
    advanced.add_argument(
        "-ar",
        "--no-auto-resume",
        help="Cleanup temp .part files\nNote this removes the ability to resume from downloads",
        default=False,
        action="store_true",
    )

    advanced.add_argument(
        "-db",
        "--downloadbars",
        help="show individual download progress bars",
        default=False,
        action="store_true",
    )

    advanced.add_argument(
        "-sd",
        "--downloadsems",
        help="Number of sems or concurrent downloads per thread",
        default=None,
        type=int,
    )

    advanced.add_argument(
        "-dp",
        "--downloadthreads",
        help="Number threads to use minimum will always be 1, Maximmum will never be higher then max availible-1",
        default=None,
        type=int,
    )

    advanced.add_argument(
        "-up",
        "--update-profile",
        help="get up to date profile info instead of using cache",
        default=False,
        action="store_true",
    )
    group11 = advanced.add_mutually_exclusive_group()

    group11.add_argument(
        "-fi",
        "--individual",
        help="When --username arg is provided searches each username as a seperate request",
        default=False,
        action="store_true",
    )

    group11.add_argument(
        "-fl",
        "--list",
        help="When --username arg is provided searches entire enabled list(s) before filtering for usernames",
        default=False,
        action="store_true",
    )

    group12 = advanced.add_mutually_exclusive_group()
    group12.add_argument(
        "-md",
        "--metadata",
        help="Skip all media downloads and gathers metadata only\nNo change to download status in media table",
        default=None,
        action="store_const",
        dest="metadata",
        const="none",
    )
    group12.add_argument(
        "-mu",
        "--metadata-update",
        help="Skip all media downloads and gathers metadata only\nUpdates downloaded status in media table based on file presence",
        default=None,
        action="store_const",
        dest="metadata",
        const="file",
    )
    group12.add_argument(
        "-mc",
        "--metadata-complete",
        help="Skip all media downloads and gathers metadata only\nMarks each media item as downloaded in media table",
        default=None,
        action="store_const",
        dest="metadata",
        const="complete",
    )

    subparser = parser.add_subparsers(help="commands", dest="command")
    post_check = subparser.add_parser(
        "post_check",
        help="Generate a table of key information from model-extracted posts\nCache lasts for 24 hours",
        parents=[parent_parser],
    )

    post_check.add_argument(
        "-u",
        "--url",
        help="Scan posts via url",
        default=None,
        required=False,
        type=helpers.check_strhelper,
        action="extend",
    )

    post_check.add_argument(
        "-f",
        "--file",
        help="Scan posts via file\nWith line seperated URL(s)",
        default=None,
        required=False,
        type=helpers.check_filehelper,
    )

    post_check.add_argument(
        "-fo",
        "--force",
        help="force retrieval of new posts info from API",
        default=False,
        action="store_true",
    )

    message_check = subparser.add_parser(
        "msg_check",
        help="Generate a table of key information from model-extracted messages\nCache lasts for 24 hours",
        parents=[parent_parser],
    )
    message_check.add_argument(
        "-fo",
        "--force",
        help="force retrieval of new messages info from API",
        default=False,
        action="store_true",
    )
    message_check.add_argument(
        "-f",
        "--file",
        help="Scan messages via file\nWith line seperated URL(s)",
        default=None,
        required=False,
        type=helpers.check_filehelper,
    )

    message_check.add_argument(
        "-u",
        "--url",
        help="scan messages via file",
        type=helpers.check_strhelper,
        action="extend",
    )

    paid_check = subparser.add_parser(
        "paid_check",
        help="Generate a table of key information from model-extracted purchases\nCache last for 24 hours",
        parents=[parent_parser],
    )
    paid_check.add_argument(
        "-fo",
        "--force",
        help="force retrieval of new purchases info from API",
        default=False,
        action="store_true",
    )
    paid_check.add_argument(
        "-f",
        "--file",
        help="Scan purchases via file\nWith line seperated usernames(s)",
        default=None,
        required=False,
        type=helpers.check_filehelper,
    )

    paid_check.add_argument(
        "-u",
        "--username",
        help="Scan purchases via usernames",
        type=helpers.check_strhelper,
        action="extend",
    )

    story_check = subparser.add_parser(
        "story_check",
        help="Generate a table of key information from model-extracted story/highlights\nCache last for 24 hours",
        parents=[parent_parser],
    )
    story_check.add_argument(
        "-fo",
        "--force",
        help="force retrieval of new posts info from API",
        default=False,
        action="store_true",
    )
    story_check.add_argument(
        "-f",
        "--file",
        help="Scan mevia file",
        default=None,
        required=False,
        type=helpers.check_filehelper,
    )

    story_check.add_argument(
        "-u",
        "--username",
        help="link to conversation",
        type=helpers.check_strhelper,
        action="extend",
    )

    manual = subparser.add_parser(
        "manual",
        help="Manually download content via url or ID",
        parents=[parent_parser],
    )
    manual.add_argument(
        "-f",
        "--file",
        help="Pass links/IDs to download via file",
        default=None,
        required=False,
        type=helpers.check_filehelper,
    )
    manual.add_argument(
        "-u",
        "--url",
        help="pass links to download via url",
        type=helpers.check_strhelper,
        action="extend",
    )

    return parser


def parse_args(input=None):
    parser = create_parser(input)

    args = parser.parse_args(input)

    # fix args
    args.username = set(args.username or [])
    args.excluded_username = set(args.excluded_username or [])
    args.label = set(args.label) if args.label else args.label
    if args.command in set(["post_check", "msg_check"]) and not (args.url or args.file):
        raise argparse.ArgumentTypeError(
            "error: argument missing --url or --file must be specified )"
        )
    elif args.command in set(["story_check", "paid_check"]) and not (
        args.username or args.file
    ):
        raise argparse.ArgumentTypeError(
            "error: argument missing --username or --file must be specified )"
        )
    elif args.command in set(["manual"]) and not (args.url or args.file):
        raise argparse.ArgumentTypeError(
            "error: argument missing --url or --file must be specified )"
        )
    write_args.setArgs(args)
    return args
