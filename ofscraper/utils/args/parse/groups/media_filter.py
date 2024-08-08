import cloup as click

from ofscraper.utils.args.parse.arguments.media_type import (
    length_max,
    length_min,
    max_size_option,
    media_id_filter,
    media_type_option,
    min_size_option,
    normal_only,
    protected_only,
    quality_option,
)
media_filter_options_desc="Media Filters Options"
media_filter_options_help="Options for controlling which media is downloaded"
# Create the option group
media_filter_options = click.option_group(
    media_filter_options_desc,
    quality_option,
    media_type_option,
    max_size_option,
    min_size_option,
    length_max,
    length_min,
    click.constraints.mutually_exclusive(
        protected_only,
        normal_only,
    ),
    media_id_filter,
    help=media_filter_options_help
)
