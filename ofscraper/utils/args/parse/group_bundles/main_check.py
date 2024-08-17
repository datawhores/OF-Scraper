import click
import functools
from ofscraper.utils.args.parse.arguments.check import (
    force,
    text_only_option,
    text_option,
)


def main_check(func):
    @force
    @text_option
    @text_only_option
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
