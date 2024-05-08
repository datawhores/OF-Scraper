# Define individual options
import itertools

import cloup as click

# import click
from humanfriendly import parse_size

import ofscraper.utils.args.helpers as helpers

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
    type=helpers.mediatype_helper,
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

# Create the option group
media_type_options = click.option_group(
    "Media Filters Options",
    quality_option,
    media_type_option,
    max_size_option,
    min_size_option,
    help="Options for controlling which media is downloaded",
)
