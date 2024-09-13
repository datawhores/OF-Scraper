import cloup as click

from ofscraper.utils.args.parse.group_bundles.metadata import metadata_args
import ofscraper.utils.args.parse.arguments.utils.retry as retry_helper


@metadata_args
@click.pass_context
def metadata(ctx, *args, **kwargs):
    ctx=retry_helper.retry_modifiy(ctx)
    return ctx.params, ctx.info_name
