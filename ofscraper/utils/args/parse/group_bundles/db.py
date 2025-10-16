import pathlib
import cloup as click

from ofscraper.utils.args.parse.groups.program import program_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.arguments.post_content import (
    db_sort_option,
    db_desc_option,
    db_posts_option,
)

from ofscraper.utils.args.parse.groups.media_filter import (
    media_type_option,
    max_size_option,
    min_size_option,
    length_max,
    length_min,
    media_filter_options_desc,
    max_media_count_option,
)
from ofscraper.utils.args.parse.groups.user_list import userlist_options
from ofscraper.utils.args.parse.groups.user_select import user_select_options
from ofscraper.utils.args.parse.groups.user_sort import user_sorting_options
from ofscraper.utils.args.parse.arguments.metadata_filters import (
    downloaded_option,
    lock_option,
    check_post_id_filter_option,
    check_media_id_filter_option,
    preview_option,
    created_after,
    created_before,
    posted_after,
    posted_before,
)


from ofscraper.utils.args.parse.groups.advanced_user_filter import (
    advanced_userfilters_options,
)


from ofscraper.utils.args.parse.groups.advanced_program import (
    advanced_options_desc,
    advanced_options_help,
    update_profile_option,
)
from ofscraper.utils.args.parse.arguments.post_content import (
    download_type_option,
)


def db_args(func):
    @click.command(
        "db",
        help="Print information from the database",
        short_help="print information from the database",
        show_constraints=True,
    )
    @click.option(
        "-ep",
        "--export",
        help="export the table as a csv file",
        type=click.Path(
            path_type=pathlib.Path,
            writable=True,
            resolve_path=True,
            dir_okay=False,
            file_okay=True,
        ),
    )
    @program_options
    @logging_options
    @click.option_group(
        "Sorting for the table",
        db_posts_option,
        db_sort_option,
        db_desc_option,
        max_media_count_option,
        help="Select hard limit and sorting for retrived items",
    )
    @click.option_group(
        media_filter_options_desc,
        media_type_option,
        min_size_option,
        max_size_option,
        length_min,
        length_max,
        lock_option,
        preview_option,
        downloaded_option,
        download_type_option,
        posted_before,
        posted_after,
        created_before,
        created_after,
        check_media_id_filter_option,
        check_post_id_filter_option,
        help="Filter based on properties of the media in the database",
    )
    @user_select_options
    @userlist_options
    @advanced_userfilters_options
    @user_sorting_options
    @click.option_group(
        advanced_options_desc, update_profile_option, help=advanced_options_help
    )
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
