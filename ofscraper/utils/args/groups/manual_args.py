import itertools

import cloup as click

import ofscraper.utils.args.groups.common_args as common
import ofscraper.utils.args.helpers as helpers


@click.command("manual", help="Manually download content via url or ID")
@click.constraints.require_one(
    click.option(
        "-u",
        "--url",
        help="A space or comma seperated list of urls to download",
        default=None,
        multiple=True,
        type=helpers.check_strhelper,
    ),
    click.option(
        "-f",
        "--file",
        help="file with line-separated URL(s) for downloading",
        default=None,
        type=helpers.check_filehelper,
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
@common.common_params
@common.common_other_params
@click.pass_context
def manual(ctx, *args, **kwargs):
    return ctx.params, ctx.invoked_subcommand
