import cloup as click
from ofscraper.utils.args.parse.arguments.media_type import quality_option,media_id_filter,media_type_option,max_size_option,min_size_option,protected_only,normal_only,length_max,length_min
# Create the option group
media_type_options = click.option_group(
    "Media Filters Options",
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
    help="Options for controlling which media is downloaded",
)