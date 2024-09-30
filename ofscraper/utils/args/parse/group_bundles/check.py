import cloup as click
import functools
from ofscraper.utils.args.parse.arguments.check import (
    force,
    text_only_option,
    text_option,
)
from ofscraper.utils.args.parse.groups.media_filter import (
    length_max,
    length_min,
    max_size_option,
    media_type_option,
    min_size_option,
    quality_option,
    media_sort_option,
    media_desc_option,
    media_filter_options_desc,
    media_filter_options_help
)
from ofscraper.utils.args.parse.groups.download import download_options
from ofscraper.utils.args.parse.groups.file import file_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.program import program_options




def main_check(func):
    @force
    @text_option
    @text_only_option
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper


def common_args_check(func):
    @program_options
    @logging_options
    @download_options
    @click.option_group(
    media_filter_options_desc,
    length_max,
    length_min,
    max_size_option,
    min_size_option,
    media_type_option,
    quality_option,
    media_sort_option,
    media_desc_option,
    help=media_filter_options_help
    )
    @file_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper