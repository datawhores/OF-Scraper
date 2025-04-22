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
    "-md",
    "--media-id",
    help="Filter media based on media id",
    required=False,
    type=click.STRING,
)

lock_option = click.option(
    "-ul/-l",
    "--unlocked/--locked",
    "unlocked",
    help="""
        \b
        Flag for filtering accounts based on whether media is unlocked
        [select one --unlock or --locked]""",
    default=None,
    required=False,
    is_flag=True,
)

downloaded_option = click.option(
    "-dl/-ndl",
    "--downloaded/--not-downloaded",
    "downloaded",
    help="""
        \b
        Flag for filtering accounts based on whether media is downloaded
        [select one --downloaded or --not-downloaded]""",
    default=None,
    required=False,
    is_flag=True,
)

posted_after = click.option(
    "-pf",
    "--posted-after",
    help="Filter out posts posted on or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
)
posted_before = click.option(
    "-pb",
    "--posted-before",
    help="Filter out posts posted at on or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
)


created_after = click.option(
    "-cf",
    "--created-after",
    help="Process media created at or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
)
created_before = click.option(
    "-cb",
    "--created-before",
    help="Process media  created at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
)


preview_option = click.option(
    "-p/-np",
    "--preview/--no-preview",
    "preview",
    help="""
        \b
        Flag for filtering accounts based on preview status.
        [select one --preview or --no-preview]""",
    default=None,
    required=False,
    is_flag=True,
)


download_type_option = preview_option = click.option(
    "-no/-to",
    "--normal-only/--protected_only",
    "download_type_filter",
    help="""
        \b
        Type of downloda to retrict to """,
    default=None,
    required=False,
)
