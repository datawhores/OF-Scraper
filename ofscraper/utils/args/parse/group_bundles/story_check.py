import cloup as click

from ofscraper.utils.args.parse.arguments.check import force
from ofscraper.utils.args.parse.groups.check_content import username_group
from ofscraper.utils.args.parse.group_bundles.advanced_common import advanced_args
from ofscraper.utils.args.parse.group_bundles.common import common_args
from ofscraper.utils.args.parse.group_bundles.utils.check import check_mode_changes
from ofscraper.utils.args.helpers.hide_args import hide_check_mode


def story_check_args(func):

    @click.command(
        "story_check",
        short_help="""\b
                Produces a media table from stories and highlights with filterable entries and quick downloads""",
        help="""
    The story_check subcommand gathers information on media content from stories and highlights
    It presents this data in a table format with filtering options for focused searches 
    Allows unlocked media entries to be directly downloaded through the table
    """,
    )
    @username_group
    @force
    @common_args
    @advanced_args
    @check_mode_changes
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    hide_check_mode(wrapper)

    return wrapper
