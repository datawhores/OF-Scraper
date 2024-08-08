import cloup as click

from ofscraper.utils.args.callbacks.file import FileCallback
from ofscraper.utils.args.callbacks.string import StringSplitParse
from ofscraper.utils.args.parse.group_bundles.advanced_common import advanced_args
from ofscraper.utils.args.parse.group_bundles.common import common_args
from  ofscraper.utils.args.helpers.hide_args import hide_manual_mode



def manual_args(func):
    @click.command(
        "manual",
        help="Manually download media by providing a list of urls or IDs",
        short_help="Manually download media by providing a list of urls or IDs",
    )
    @common_args
    @click.constraints.require_one(
        click.option(
            "-u",
            "--url",
            help="A space or comma seperated list of urls to download",
            default=None,
            multiple=True,
            callback=StringSplitParse,
        ),
        click.option(
            "-f",
            "--file",
            help="file with line-separated URL(s) for downloading",
            default=None,
            type=click.File(),
            multiple=True,
            callback=FileCallback,
        ),
    )
    @click.option(
        "-fo",
        "--force",
        help="Force retrieval of new messages info from API",
        is_flag=True,
        default=False,
    )
    @advanced_args
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)
    hide_manual_mode(wrapper)
    return wrapper
