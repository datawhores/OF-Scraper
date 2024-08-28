import cloup as click

from ofscraper.utils.args.parse.arguments.content import (
    after_option,
    before_option,
    block_ads_option,
    download_area_option,
    filter_option,
    force_all_option,
    force_model_unique_option,
    redownload_option,
    media_sort_option,
    media_desc_option,
    post_sort_option,
    post_desc_option,
    label_option,
    like_area_option,
    like_toggle_force,
    mass_msg_option,
    max_count_option,
    neg_filter_option,
    post_id_filter,
    posts_option,
    scrape_paid_option,
    timed_only_option,
    timeline_strict,
    text_option,
)


content_options_desc = "Content Options"
content_options_help = """
    \b
    Define what posts to target (areas, filters) and actions to perform (like, unlike, download)
    Filter by type, date, label, size, and media type"""
content_options_tuple = (
    posts_option,
    download_area_option,
    like_area_option,
    post_id_filter,
    filter_option,
    neg_filter_option,
    scrape_paid_option,
    block_ads_option,
    max_count_option,
    media_sort_option,
    media_desc_option,
    post_sort_option,
    post_desc_option,
    redownload_option,
    force_all_option,
    force_model_unique_option,
    like_toggle_force,
    label_option,
    text_option,
    before_option,
    after_option,
    mass_msg_option,
    timed_only_option,
    timeline_strict,
)
content_options = click.option_group(
    content_options_desc,
    *content_options_tuple,
    help=content_options_help,
)
