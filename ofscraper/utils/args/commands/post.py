import cloup as click

from ofscraper.utils.args.bundles.post_check import post_check_args


@post_check_args
@click.pass_context
def post_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
