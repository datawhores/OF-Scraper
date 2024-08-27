import cloup as click

from ofscraper.utils.args.parse.group_bundles.advanced_common import advanced_args
from ofscraper.utils.args.parse.group_bundles.common import common_args
from ofscraper.utils.args.helpers.hide_args import hide_manual_mode
from ofscraper.utils.args.parse.groups.check_content import url_group
from ofscraper.utils.args.parse.group_bundles.main_check import main_check


def manual_args(func):
    @click.command(
        "manual",
        help="Manually download media by providing a list of urls or IDs",
        short_help="Manually download media by providing a list of urls or IDs",
    )
    @common_args
    @main_check
    @url_group
    @advanced_args
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    hide_manual_mode(wrapper)
    return wrapper
