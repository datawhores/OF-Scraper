import itertools

import cloup as click

import ofscraper.utils.args.helpers.type as type
from ofscraper.utils.args.bundles.advanced_common import advanced_args
from ofscraper.utils.args.bundles.common import common_args


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
            type=type.check_strhelper,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
        ),
        click.option(
            "-f",
            "--file",
            help="file with line-separated URL(s) for downloading",
            default=None,
            type=type.check_filehelper,
            multiple=True,
            callback=lambda ctx, param, value: (
                list(set(itertools.chain.from_iterable(value))) if value else []
            ),
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

    return wrapper
