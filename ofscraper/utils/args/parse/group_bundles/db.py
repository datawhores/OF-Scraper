import cloup as click

from ofscraper.utils.args.parse.groups.program import program_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.content import (
    content_options_help,
    content_options_desc,
    after_option,
    before_option,
    filter_option,
    label_option,
    max_count_option,
    neg_filter_option,
    posts_option,
)
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





def db_args(func):
    @click.command(
        "db",
        help="Print information from the database",
        short_help="print information from the database",
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
    @program_options
    @logging_options
    @click.option_group(
        content_options_desc,
        posts_option,
        filter_option,
        neg_filter_option,
        max_count_option,
        label_option,
        before_option,
        after_option,
        help=content_options_help,
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
