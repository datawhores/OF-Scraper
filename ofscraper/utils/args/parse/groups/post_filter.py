import cloup as click

from ofscraper.utils.args.parse.arguments.post_content import (
    post_id_filter_option,
    max_post_count_option,
    post_sort_option,
    post_desc_option,
    filter_option,
    neg_filter_option,
    label_option,
    mass_msg_option,
    timed_only_option,
    posts_option,
    download_type_option,
    scrape_paid_option,
)

post_filter_options_desc = "Posts Filters Options"
post_filter_options_help = (
    "Options for controlling which posts are liked/unliked, and in which order"
)
post_filter_options_tuple = (
    posts_option,
    download_type_option,
    post_id_filter_option,
    max_post_count_option,
    post_sort_option,
    post_desc_option,
    filter_option,
    neg_filter_option,
    label_option,
    mass_msg_option,
    timed_only_option,
    scrape_paid_option,
)
# Create the option group
post_filter_options = click.option_group(
    post_filter_options_desc, *post_filter_options_tuple, help=post_filter_options_help
)
