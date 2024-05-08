import functools

import cloup as click

# import click
from humanfriendly import parse_size

from ofscraper.utils.args.arguments.advanced_processing import (
    advanced_processing_options,
)
from ofscraper.utils.args.arguments.advanced_user_filter import (
    advanced_userfilters_options,
)
from ofscraper.utils.args.arguments.automatic import automatic_options
from ofscraper.utils.args.arguments.content import content_options
from ofscraper.utils.args.arguments.user_list import userlist_options
from ofscraper.utils.args.arguments.user_select import user_select_options
from ofscraper.utils.args.arguments.user_sort import user_sorting_options


def main_program_args(func):
    @content_options
    @automatic_options
    @user_select_options
    @userlist_options
    @advanced_userfilters_options
    @user_sorting_options
    @advanced_processing_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
