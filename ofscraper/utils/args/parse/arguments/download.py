import cloup as click
from humanfriendly import parse_size

no_auto_resume_option = click.option(
    "-ar",
    "--no-auto-resume",
    help="Clean up temp .part files (removes resume ability)",
    default=False,
    is_flag=True,
)

show_download_bars_option = click.option(
    "-db",
    "--downloadbars",
    "--download-bars",
    "--download-bar",
    "downloadbars",
    help="Show individual download progress bars",
    default=False,
    is_flag=True,
)

download_sem_option = click.option(
    "-sd",
    "--downloadsem",
    "--downloadsems",
    "--download-sems",
    "--download-sem",
    "--sems",
    "--sem",
    "download_sem",
    help="Number of downloads at the same time (overrides performance_options.download_sems).",
    default=None,
    type=int,
)

download_limit_option = click.option(
    "-dl",
    "--download-limit",
    "download_limit",
    help="""
    \b
    Maximum download speed per second.
    Accepts a human-readable size ('10MB') or bytes per second.
    """,
    default=None,
    type=parse_size,
)

allow_dupes_option = click.option(
    "-ad",
    "--allow-dupes/--no-allow-dupes",
    "--allow-dupe-downloads",
    "allow_dupe_downloads",
    help="Download media that is in several posts once for each post, instead of once (default: ALLOW_DUPE_MEDIA, off)",
    default=None,
    is_flag=True,
)

skip_purchased_dupes_option = click.option(
    "--skip-purchased-dupes",
    "skip_purchased_dupes",
    help="With --allow-dupes, skip a Purchased copy of media that's in another post or was downloaded from one. Media only in Purchased still downloads. Matches by media ID before download; remove_hash_match removes copies with different IDs",
    default=False,
    is_flag=True,
)
