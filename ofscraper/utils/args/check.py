import functools

import cloup as click

import ofscraper.utils.args.helpers.date as date_helper


def check_mode_changes(func):
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        # fix before for check modes
        ctx.params["before"] = date_helper.before_callback(ctx, ctx.params, None)

        return func(ctx, *args, **kwargs)

    return wrapper
