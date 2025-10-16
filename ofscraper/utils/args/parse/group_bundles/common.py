import functools

import cloup as click

from ofscraper.utils.args.parse.groups.download import download_options
from ofscraper.utils.args.parse.groups.file import file_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.media_filter import media_filter_options
from ofscraper.utils.args.parse.groups.program import program_options


def common_args(func):
    @program_options
    @logging_options
    @download_options
    @media_filter_options
    @file_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
