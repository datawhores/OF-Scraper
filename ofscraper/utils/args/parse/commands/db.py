import cloup as click

from ofscraper.utils.args.parse.group_bundles.db import db_args


@db_args
@click.pass_context
def db(ctx, *args, **kwargs):
    ctx.params["post_id"]=set(ctx.params["post_id"])
    ctx.params["media_id"]=set(ctx.params["media_id"])
    return ctx.params, ctx.info_name
