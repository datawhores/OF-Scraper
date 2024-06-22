import cloup as click

from ofscraper.utils.args.parse.group_bundles.message_check import message_check_args


@message_check_args
@click.pass_context
def message_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
