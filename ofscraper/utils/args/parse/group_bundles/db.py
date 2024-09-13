import pathlib
import cloup as click

from ofscraper.utils.args.parse.groups.program import program_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.content import (
    content_options_help,
    content_options_desc,
    max_count_option,
    post_id_filter,
)
from ofscraper.utils.args.parse.groups.media_filter import(
media_type_option,
max_size_option,
min_size_option,
media_filter_options_desc,
media_id_filter,
length_max,
length_min,
media_filter_options_help
)
from ofscraper.utils.args.parse.arguments.content import db_posts_option, db_sort_option,db_desc_option
from ofscraper.utils.args.parse.groups.user_list import userlist_options
from ofscraper.utils.args.parse.groups.user_select import user_select_options
from ofscraper.utils.args.parse.groups.user_sort import user_sorting_options
from ofscraper.utils.args.parse.groups.advanced_user_filter import (
    advanced_userfilters_options,
)


from ofscraper.utils.args.parse.groups.advanced_program import (
   advanced_options_desc,
   advanced_options_help,
   update_profile_option
)
from ofscraper.utils.args.types.arrow import ArrowType







def db_args(func):
    @click.command(
        "db",
        help="Print information from the database",
        short_help="print information from the database",
    )
    @click.option(
    "-ep",
    "--export",
    help="export the table as a csv file",
    type=click.Path(path_type=pathlib.Path,writable=True,resolve_path=True,dir_okay=False,file_okay=True),
)
    @click.constraints.mutually_exclusive(
    click.option(
    "-dl",
    "--downloaded",
    "downloaded",
    is_flag=True,
    default=False

),
click.option(
    "-nl",
    "--not-downloaded",
    "not_downloaded",
    is_flag=True,
    default=False

))
    @click.constraints.mutually_exclusive(
    click.option(
    "-ul",
    "--unlocked",
    "unlocked",
    is_flag=True,
    default=False

),
click.option(
    "-l",
    "--locked",
    "locked",
    is_flag=True,
    default=False

))
    @click.constraints.mutually_exclusive(
    click.option(
    "-np",
    "--no-preview",
    "no_preview",
    is_flag=True,
    default=False

),
click.option(
    "-p",
    "--preview",
    "preview",
    is_flag=True,
    default=False

))
    @program_options
    @logging_options
    @click.option_group(
        content_options_desc,
        db_posts_option,
        max_count_option,
        post_id_filter,
        db_sort_option,
        db_desc_option,
        click.option(
    "-cf",
    "--created-after",
    help="Process media created at or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
),

    click.option(
    "-cb",
    "--created-before",
    help="Process media  created at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
),

   click.option(
    "-pf",
    "--posted-after",
    help="Process posts posted or after the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
),

    click.option(
    "-pb",
    "--posted-before",
    help="Process posts posted at or before the given date (MM/DD/YYYY) for likes, unlikes, and downloads",
    type=ArrowType(),
),

        help=content_options_help,
    )
    @click.option_group(
    media_filter_options_desc,
    media_type_option,
    min_size_option,
    max_size_option,
    length_min,
    length_max,
    media_id_filter,
    help=media_filter_options_help
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
