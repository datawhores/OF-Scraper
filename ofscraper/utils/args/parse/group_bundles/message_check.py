import cloup as click


from ofscraper.utils.args.parse.groups.check_content import url_group
from ofscraper.utils.args.parse.group_bundles.check import main_check, common_args_check
from ofscraper.utils.args.parse.group_bundles.advanced_common import advanced_args
from ofscraper.utils.args.parse.group_bundles.utils.check import check_mode_changes
from ofscraper.utils.args.helpers.hide_args import hide_check_mode


def message_check_args(func):

    @click.command(
        "post_check",
        short_help="""\b
                Produces a media table from posts with filterable entries and quick downloads""",
        help="""The post_check subcommand gathers information on media content from posts
    It presents this data in a table format with filtering options for focused searches 
    Allows unlocked media entries to be directly downloaded through the table""",
        show_constraints=True,
    )
    @common_args_check
    @url_group
    @main_check
    @advanced_args
    @check_mode_changes
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    hide_check_mode(wrapper)

    return wrapper
