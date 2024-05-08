import functools

import cloup as click

from ofscraper.utils.args.arguments.download import download_options
from ofscraper.utils.args.arguments.file import file_options
from ofscraper.utils.args.arguments.logging import logging_options
from ofscraper.utils.args.arguments.media_type import media_type_options
from ofscraper.utils.args.arguments.program import program_options


def common_args(func):
    @program_options
    @logging_options
    @download_options
    @media_type_options
    @file_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
