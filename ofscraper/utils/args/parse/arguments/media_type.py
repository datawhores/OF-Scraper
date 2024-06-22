# Define individual options
import itertools

import cloup as click

# import click
from humanfriendly import parse_size

import ofscraper.utils.args.parse.arguments.helpers.type as type

quality_option = click.option(
    "-q",
    "--quality",
    type=click.Choice(["240", "720", "source"], case_sensitive=False),
)

media_type_option = click.option(
    "-mt",
    "--mediatype",
    help="Filter by media type (Videos, Audios, Images)",
    default=[],
    required=False,
    type=type.mediatype_helper,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
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

protected_only = click.option(
    "-to",
    "--protected-only",
    help="Restricts downloads to content that requires decryption.",
    required=False,
    is_flag=True,
)

normal_only = click.option(
    "-no",
    "--normal-only",
    help="Restricts downloads to content that does not require decryption.",
    required=False,
    is_flag=True,
)

media_id_filter = click.option(
    "-md",
    "--media-id",
    help="Filter media based on media id",
    required=False,
    callback=lambda ctx, param, value: (
        list(set(itertools.chain.from_iterable(value))) if value else []
    ),
    type=type.string_split_helper,
    multiple=True,
)

length_max=click.option(
        "-lx",
        "-length-max",
        help="max duration in seconds does not effect non-media files",
        required=False,
        type=parse_size,
    )
length_min=click.option(
        "-lm",
        "--length-min",
        help="min duration in seconds does not effect non-media files",
        required=False,
        type=parse_size,
    ),

