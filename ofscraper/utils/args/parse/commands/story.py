import cloup as click

from ofscraper.utils.args.parse.group_bundles.story_check import story_check_args


@story_check_args
@click.pass_context
def story_check(ctx, *args, **kwargs):
    return ctx.params, ctx.info_name
