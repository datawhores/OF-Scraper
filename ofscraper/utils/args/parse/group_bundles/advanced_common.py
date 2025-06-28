import functools

import cloup as click

from ofscraper.utils.args.parse.groups.advanced_program import advanced_options
from ofscraper.utils.args.parse.groups.scripts import script_options


def advanced_args(func):
    @script_options
    @advanced_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
