import cloup as click

import ofscraper.utils.args.parse.arguments.utils.date as date_helper
from ofscraper.utils.args.callbacks.string import (
    StringSplitNormalizeParse,
    StringSplitParse,
    StringSplitParseTitle,
    StringTupleList,
)
from ofscraper.utils.args.types.arrow import ArrowType
from ofscraper.utils.args.types.choice import MultiChoice,MultiChoicePost

# Define individual options
posts_option = click.option(
    "-o",
    "--posts",
    "--post",
    "posts",
    help="""
    Select areas for batch actions (comma or space separated).
    Options: HighLights, Archived, Messages, Timeline, Pinned, Stories, Purchased, Profile, Labels, All
    """,
    default=[],
    required=False,
    type=MultiChoicePost(
        [
            "Highlights",
            "All",
            "Archived",
            "Messages",
            "Timeline",
            "Pinned",
            "Streams",
            "Stories",
            "Purchased",
            "Profile",
            "Labels",
            "Labels+",
            "Labels*",
        ],
        case_sensitive=False,
    ),
    callback=StringSplitParseTitle,
    multiple=True,
)

download_area_option = click.option(
    "-da",
    "--download-area",
    "download_area",
    help="""
    Perform download in specified areas (comma or space separated).
    Options: HighLights, Archived, Messages, Timeline, Pinned, Stories, Purchased, Profile, Labels, All
    Has preference over --posts for download action
    """,
    default=[],
    required=False,
    type=MultiChoice(
        [
            "Highlights",
            "All",
            "Archived",
            "Messages",
            "Timeline",
            "Pinned",
            "Stread_args.retriveArgs().download_areaories",
            "Purchased",
            "Profile",
            "Streams",
            "Labels",
            "Labels+",
            "Labels*",
        ],
        case_sensitive=False,
    ),
    callback=StringSplitParseTitle,
    multiple=True,
)

like_area_option = click.option(
    "-la",
    "--like-area",
    help="""
    Perform like/unlike in selected areas (comma or space separated).
    Options: Archived, Timeline,fo Pinned, Labels, All
    Has preference over --posts for like action
    """,
    default=[],
    required=False,
    type=MultiChoice(
        ["All", "Archived", "Timeline", "Pinned", "Labels", "Streams"],
        case_sensitive=False,
    ),
    callback=StringSplitParseTitle,
    multiple=True,
)

filter_option = click.option(
    "-ft",
    "--filter",
    help="Filter posts by regex (case-sensitive if uppercase characters included)",
    default=[".*"],
    required=False,
    callback=StringTupleList,
    multiple=True,
)

neg_filter_option = click.option(
    "-nf",
    "--neg-filter",
    help="Filter posts to exclude those matching regex (case-styensitive if uppercase characters included)",
    default=[],
    required=False,
    type=str,
    multiple=True,
    callback=StringTupleList,
)

block_ads_option = click.option(
    "-ba",
    "--block-ads",
    help="Filter posts with regex to block posts with common words for advertisements",
    default=False,
    is_flag=True,
)

# allow_ads_option = click.option(
#     "-aa",
#     "--allow-ads",
#     help="Allows posts with common advertisment words",
#     default=False,
#     is_flag=True,
# )


scrape_paid_option = click.option(
    "-sp",
    "--scrape-paid",
    help="Scrape entire paid page (can take a very long time)",
    default=False,
    is_flag=True,
)

max_count_option = click.option(
    "-xc",
    "--max-count",
    help="Maximum number of posts to download",
    default=0,
    type=int,
)

item_sort_option = click.option(
    "-it",
    "--item-sort",
    help="Changes media processing order before action (default: date asc or random)",
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
)

force_all_option = click.option(
    "-e",
    "--force-all",
    "--dupe",
    "--dupe-all",
    "force_all",
    help="Download all files regardless of database presence",
    default=False,
    is_flag=True,
)

force_model_unique_option = click.option(
    "-eq",
    "--force-model-unique",
    "--dupe-model-unique",
    "--dupe-model",
    "--force_model_unique",
    help="Only download files with media ids not present for the current model in the database",
    default=False,
    is_flag=True,
)

like_toggle_force = click.option(
    "-fl",
    "--force-like",
    "--force-like-toggle",
    "--no-cache-like",
    "force_like",
    help="force toggling of posts to like or unlike status regardless of cache",
    default=False,
    is_flag=True,
)

label_option = click.option(
    "-lb",
    "--label",
    help="Filter by label (use helpers.label_helper to process)",
    default=[],
    required=False,
    callback=StringSplitNormalizeParse,
    multiple=True,
)
before_option = click.option(
    "-be",
    "--before",
    help="Process posts at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
    callback=lambda ctx, param, value: date_helper.before_callback(ctx, param, value),
)

after_option = click.option(
    "-af",
    "--after",
    help="Process posts at or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
)

mass_msg_option = click.option(
    "-mm/-ms",
    "--mass-only/--mass-skip",
    "mass_msg",
    help="""
    \b
    Flag for enabling/disabling mass content or promos 
    [select one --mass-only or --mass-skip]""",
    default=None,
    required=False,
)

timed_only_option = click.option(
    "-ok/-sk",
    "--only-timed/--skip-timed",
    "timed_only",
    default=None,
    help="""
    \b
    Flag for enabling/disabling promotional or temporary posts
    [select one --only-timed or --skip-timed]""",
)

post_id_filter = click.option(
    "-pd",
    "--post-id",
    "--url",
    "post_id",
    help="Filter posts based on post id",
    required=False,
    callback=StringSplitParse,
    multiple=True,
    type=click.STRING,
)

timeline_strict = click.option(
    "-tls",
    "--timeline-strict",
    help="When timeline is select removes pinned and archived",
    default=False,
    is_flag=True,
)
