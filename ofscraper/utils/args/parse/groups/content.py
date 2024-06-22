
import cloup as click
from ofscraper.utils.args.parse.arguments.content import post_id_filter,posts_option,like_area_option,like_toggle_force,filter_option,force_all_option,force_model_unique_option,neg_filter_option,download_area_option,scrape_paid_option,max_count_option,item_sort_option,label_option,before_option,after_option,mass_msg_option,timed_only_option,timeline_strict
content_options = click.option_group(
    "Content Options",
    posts_option,
    download_area_option,
    like_area_option,
    post_id_filter,
    filter_option,
    neg_filter_option,
    scrape_paid_option,
    max_count_option,
    item_sort_option,
    force_all_option,
    force_model_unique_option,
    like_toggle_force,
    label_option,
    before_option,
    after_option,
    mass_msg_option,
    timed_only_option,
    timeline_strict,
    help="""
    \b
    Define what posts to target (areas, filters) and actions to perform (like, unlike, download)
    Filter by type, date, label, size, and media type""",
)