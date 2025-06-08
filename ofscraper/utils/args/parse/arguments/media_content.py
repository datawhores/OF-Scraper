import cloup as click

# import click
from humanfriendly import parse_size

from ofscraper.utils.args.callbacks.parse.string import (
    StringSplitParse,
    StringSplitParseTitle,
)
from ofscraper.utils.args.types.choice import MultiChoice
from ofscraper.utils.args.types.arrow import ArrowType
import ofscraper.utils.args.parse.arguments.utils.date as date_helper

quality_option = click.option(
    "-q",
    "--quality",
    type=click.Choice(["240", "720", "source"], case_sensitive=False),
)

media_type_option = click.option(
    "-mt",
    "--mediatype",
    "mediatype",
    help="Filter by media type (Videos, Audios, Images)",
    default=[],
    required=False,
    type=MultiChoice(["Videos", "Audios", "Images"], case_sensitive=False),
    callback=StringSplitParseTitle,
    multiple=True,
)

max_size_option = click.option(
    "-sx",
    "--size-max",
    help="Filter out files larger than the given size (bytes or human-readable, e.g., 10mb)",
    required=False,
    type=parse_size,
)

min_size_option = click.option(
    "-sm",
    "--size-min",
    help="Filter out files smaller than the given size (bytes or human-readable, e.g., 10mb)",
    required=False,
    type=parse_size,
)


media_id_filter = click.option(
    "-mid",
    "--media-id",
    help="Filter media based on media id",
    required=False,
    callback=StringSplitParse,
    multiple=True,
    type=click.STRING,
)

length_max = click.option(
    "-lx",
    "--length-max",
    help="max duration in seconds only effects videos and audios",
    required=False,
    type=parse_size,
)
length_min = click.option(
    "-lm",
    "--length-min",
    help="min duration in seconds only effects videos and audios",
    required=False,
    type=parse_size,
)


max_media_count_option = click.option(
    "-mxc",
    "--max-media-count",
    "max_count",
    help="Maximum number of media to process",
    default=0,
    type=int,
)

media_sort_option = click.option(
    "-mst",
    "--media-sort",
    "mediasort",
    help="""
    \b
    Changes media processing order before actions
    Example: for download
    """,
    default=None,
    required=False,
    type=click.Choice(
        [
            "random",
            "text",
            "text",
            "date",
            "filename",
        ]
    ),
)

media_desc_option = click.option(
    "-mdc",
    "--media-desc",
    help="""
    \b
    Sort the media list in descending order
    """,
    is_flag=True,
    default=False,
)


force_all_option = click.option(
    "-e",
    "--force-all",
    "--dupe",
    "--dupe-all",
    "force_all",
    help="Download all found files regardless of database presence",
    default=False,
    is_flag=True,
)

force_model_unique_option = click.option(
    "-eq",
    "--force-model-unique",
    "--dupe-model-unique",
    "--dupe-model",
    "--force_model_unique",
    help="Only download found files with media ids not present for the current model in the database",
    default=False,
    is_flag=True,
)

before_option = click.option(
    "-be",
    "--before",
    help="Process media from posts at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
    callback=lambda ctx, param, value: date_helper.before_callback(ctx, param, value),
)

after_option = click.option(
    "-af",
    "--after",
    help="Process media from posts at or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
)

redownload_option = click.option(
    "-rd",
    "--redownload",
    "--re-download",
    "redownload",
    help="Forces redownloading of all files in selected post types",
    default=False,
    is_flag=True,
)
