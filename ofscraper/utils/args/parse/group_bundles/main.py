import functools

import cloup as click

from ofscraper.utils.args.parse.groups.advanced_processing import (
    advanced_processing_options,
)
from ofscraper.utils.args.parse.groups.advanced_user_filter import (
    advanced_userfilters_options,
)
from ofscraper.utils.args.parse.groups.automatic import automatic_options
from ofscraper.utils.args.parse.groups.post_filter import post_filter_options
from ofscraper.utils.args.parse.groups.user_list import userlist_options
from ofscraper.utils.args.parse.groups.user_select import user_select_options
from ofscraper.utils.args.parse.groups.user_sort import user_sorting_options
from ofscraper.utils.args.parse.group_bundles.common import common_args

# import click


def main_program_args(func):
    @common_args
    @post_filter_options
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
