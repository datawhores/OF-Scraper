import cloup as click

from ofscraper.utils.args.callbacks.parse.string import (
    StringSplitNormalizeParse,
    StringSplitParse,
    StringSplitParseTitle,
    StringTupleList,
)
from ofscraper.utils.args.callbacks.arguments.post import set_download_type_flag
from ofscraper.utils.args.types.choice import MultiChoice, MultiChoicePost

# Define individual options
posts_option = click.option(
    "-o",
    "--posts",
    "--post",
    "posts",
    help="""
    Select areas for batch actions (comma or space separated).
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

db_posts_option = click.option(
    "-o",
    "--posts",
    "--post",
    "posts",
    help="""
    Select areas for batch actions (comma or space separated)
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
            "Profile",
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
            "Stsettings.get_settings().download_areaories",
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
    help="""
    \b
    Filter posts by regex 
    (case-sensitive if uppercase characters included)
    uses raw python string
    """,
    default=[".*"],
    required=False,
    callback=StringTupleList,
    multiple=True,
)

neg_filter_option = click.option(
    "-nf",
    "--neg-filter",
    help="""
    \b
    Filter posts to exclude those matching regex 
    (case-styensitive if uppercase characters included)
    uses raw python string
    """,
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


text_option = click.option(
    "-t",
    "--text",
    "--download-text",
    "download_text",
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
    help="""
    Download Text files
    options are based on the --mediatype option
    """,
    default="",
)


scrape_paid_option = click.option(
    "-sp",
    "--scrape-paid",
    help="Scrape entire paid page (can take a very long time)",
    default=False,
    is_flag=True,
)

post_sort_option = click.option(
    "-pst",
    "--post-sort",
    help="""
    \b
    Changes post processing order before actions
    Example: for like or unlike
    """,
    default="date",
    required=False,
    type=click.Choice(
        [
            "date",
        ]
    ),
)

post_desc_option = click.option(
    "-pdc",
    "--post-desc",
    help="""
    Sort the post list in descending order
    Example: for like or unlike
    """,
    is_flag=True,
    default=False,
)

db_sort_option = click.option(
    "-dst",
    "--db-sort",
    help="""
    Changes order of table
    """,
    default="posted",
    required=False,
    type=click.Choice(
        ["posted", "created", "filename", "length", "postid", "mediaid", "size"]
    ),
)

db_desc_option = click.option(
    "-bdc",
    "--db-asc",
    help="""
    Change the sort order  of table to ascending
    """,
    is_flag=True,
    default=False,
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


post_id_filter_option = click.option(
    "-pd",
    "--post-id",
    "--postid",
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

download_type_option = click.option(
    "-to/-no",
    "--protected-only/--normal-only",
    "download_type",
    help="""
        \b
        Filter downloads by type.
        --protected-only: For content that requires decryption.
        --normal-only: For content that does not require decryption.
    """,
    default=None,
    callback=set_download_type_flag,
    is_flag=True # is_flag is still needed for the split flag to work
)


max_post_count_option = click.option(
    "-xc",
    "--max-post-count",
    "max_count",
    help="Maximum number of posts to process",
    default=0,
    type=int,
)
