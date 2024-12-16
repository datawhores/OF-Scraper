import cloup as click

from ofscraper.utils.args.parse.arguments.media_content import (
    length_max,
    length_min,
    max_size_option,
    media_id_filter,
    media_type_option,
    min_size_option,
    quality_option,
    max_media_count_option,
    media_sort_option,
    media_desc_option,
    force_all_option,
    force_model_unique_option,
    before_option,
    after_option,
    redownload_option,
)

media_filter_options_desc = "Media Filters Options"
media_filter_options_help = (
    "Options for controlling which media is downloaded, and in which order"
)
media_filter_options_tuple = (
    quality_option,
    media_type_option,
    max_size_option,
    min_size_option,
    length_max,
    length_min,
    media_id_filter,
    max_media_count_option,
    media_sort_option,
    media_desc_option,
    force_all_option,
    force_model_unique_option,
    before_option,
    after_option,
    redownload_option,
)
# Create the option group
media_filter_options = click.option_group(
    media_filter_options_desc,
    *media_filter_options_tuple,
    help=media_filter_options_help
)
