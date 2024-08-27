import cloup as click

from ofscraper.utils.args.parse.group_bundles.db import db_args


@db_args
@click.pass_context
def db(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
