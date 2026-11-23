import cloup as click
from ofscraper.utils.args.types.arrow import ArrowType

# Filter/sort retrived metadata

check_post_id_filter_option = click.option(
    "-pd",
    "--post-id",
    "--postid",
    "post_id",
    help="Filter posts based on post id",
    required=False,
    # type=click.STRING,
)


check_media_id_filter_option = click.option(
    "-mid",
    "--media-id",
    help="Filter media based on media id",
    required=False,
    type=click.STRING,
)

lock_option = click.option(
    "-ucl/-lc",
    "--unlocked/--locked",
    "unlocked",
    help="""
        \b
        Filter media by whether it's unlocked.
        [select one --unlocked or --locked]""",
    default=None,
    required=False,
    is_flag=True,
)

downloaded_option = click.option(
    "-dwl/-ndw",
    "--downloaded/--not-downloaded",
    "downloaded",
    help="""
        \b
        Filter media by whether it's downloaded.
        [select one --downloaded or --not-downloaded]""",
    default=None,
    required=False,
    is_flag=True,
)

posted_after = click.option(
    "-pf",
    "--posted-after",
    help="Only media from posts posted on or after the given date (YYYY-MM-DD, MM/DD/YYYY or a relative date such as '3 weeks ago').",
    type=ArrowType(),
)
posted_before = click.option(
    "-pb",
    "--posted-before",
    help="Only media from posts posted on or before the given date (YYYY-MM-DD, MM/DD/YYYY or a relative date such as '3 weeks ago').",
    type=ArrowType(),
)


created_after = click.option(
    "-cf",
    "--created-after",
    help="Only media created on or after the given date (YYYY-MM-DD, MM/DD/YYYY or a relative date such as '3 weeks ago').",
    type=ArrowType(),
)
created_before = click.option(
    "-cb",
    "--created-before",
    help="Only media created on or before the given date (YYYY-MM-DD, MM/DD/YYYY or a relative date such as '3 weeks ago').",
    type=ArrowType(),
)


preview_option = click.option(
    "-pv/-npv",
    "--preview/--no-preview",
    "preview",
    help="""
        \b
        Filter media by preview status.
        [select one --preview or --no-preview]""",
    default=None,
    required=False,
    is_flag=True,
)
