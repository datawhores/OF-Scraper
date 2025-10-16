import functools
import arrow

import cloup as click


def check_mode_changes(func):
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        # fix before for check modes
        ctx.params["before"] = arrow.now().shift(days=4)
        ctx.params["before_original"] = None
        return func(ctx, *args, **kwargs)

    return wrapper
