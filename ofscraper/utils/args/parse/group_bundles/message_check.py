import itertools

import cloup as click

import ofscraper.utils.args.parse.arguments.helpers.type as type
from ofscraper.utils.args.parse.group_bundles.advanced_common import advanced_args
from ofscraper.utils.args.parse.group_bundles.common import common_args
from ofscraper.utils.args.parse.group_bundles.helpers.check import check_mode_changes
from ofscraper.utils.args.parse.arguments.check import url_group,force


def message_check_args(func):

    @click.command(
        "post_check",
        short_help="""\b
                Produces a media table from posts with filterable entries and quick downloads""",
        help="""The post_check subcommand gathers information on media content from posts
    It presents this data in a table format with filtering options for focused searches 
    Allows unlocked media entries to be directly downloaded through the table""",
    )
    @common_args
    @url_group
    @force
    @advanced_args
    @check_mode_changes
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
