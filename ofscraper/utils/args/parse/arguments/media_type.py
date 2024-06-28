import cloup as click

# import click
from humanfriendly import parse_size

from ofscraper.utils.args.callbacks.string import (
    StringSplitParse,
    StringSplitParseTitle,
)
from ofscraper.utils.args.types.choice import MultiChoice

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
    callback=StringSplitParse,
    multiple=True,
    type=click.STRING,
)

length_max = click.option(
    "-lx",
    "--length-max",
    help="max duration in seconds does not effect non-media files",
    required=False,
    type=parse_size,
)
length_min = click.option(
    "-lm",
    "--length-min",
    help="min duration in seconds does not effect non-media files",
    required=False,
    type=parse_size,
)
