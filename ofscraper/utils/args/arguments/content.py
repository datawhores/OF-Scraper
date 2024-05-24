import itertools

import cloup as click

import ofscraper.utils.args.helpers.date as date_helper
import ofscraper.utils.args.helpers.type as type

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
    type=type.posttype_helper,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
    multiple=True,
)

download_area_option = click.option(
    "-da",
    "--download-area",
    "download_area",
    help="""
    Perform download in specified areas (comma or space separated).
    Options: HighLights, Archived, Messages, Timeline, Pinned, Stories, Purchased, Profile, Labels, All
    Has preference over --posts
    """,
    default=[],
    required=False,
    type=type.download_helper,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
    multiple=True,
)

like_area_option = click.option(
    "-la",
    "--like-area",
    help="""
    Perform like/unlike in selected areas (comma or space separated).
    Options: Archived, Timeline, Pinned, Labels, All
    Has preference over --posts
    """,
    default=[],
    required=False,
    type=type.like_helper,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
    multiple=True,
)

filter_option = click.option(
    "-ft",
    "--filter",
    help="Filter posts by regex (case-sensitive if uppercase characters included)",
    default=".*",
    required=False,
    type=str,
)

neg_filter_option = click.option(
    "-nf",
    "--neg-filter",
    help="Filter posts to exclude those matching regex (case-sensitive if uppercase characters included)",
    default=None,
    required=False,
    type=str,
)

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
    help="Maximum number of posts to download (oldest non-duped first)",
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
    type=type.label_helper,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
    multiple=True,
)
before_option = click.option(
    "-be",
    "--before",
    help="Process posts at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=type.arrow_helper,
    callback=lambda ctx, param, value: date_helper.before_callback(ctx, param, value),
)

after_option = click.option(
    "-af",
    "--after",
    help="Process posts at or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=type.arrow_helper,
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

# Create the option group

content_options = click.option_group(
    "Content Options",
    posts_option,
    download_area_option,
    like_area_option,
    filter_option,
    neg_filter_option,
    scrape_paid_option,
    max_count_option,
    item_sort_option,
    force_all_option,
    force_model_unique_option,
    like_toggle_force,
    label_option,
    before_option,
    after_option,
    mass_msg_option,
    timed_only_option,
    help="""
    \b
    Define what posts to target (areas, filters) and actions to perform (like, unlike, download)
    Filter by type, date, label, size, and media type""",
)
