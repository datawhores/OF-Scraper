import cloup as click

from ofscraper.utils.args.parse.group_bundles.metadata import metadata_args


@metadata_args
@click.pass_context
def metadata(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
