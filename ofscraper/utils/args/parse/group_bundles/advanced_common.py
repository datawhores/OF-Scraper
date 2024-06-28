import functools

import cloup as click

from ofscraper.utils.args.parse.groups.advanced_program import advanced_options


def advanced_args(func):
    @advanced_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
