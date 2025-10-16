import cloup as click

from ofscraper.utils.args.parse.group_bundles.paid_check import paid_check_args


@paid_check_args
@click.pass_context
def paid_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
