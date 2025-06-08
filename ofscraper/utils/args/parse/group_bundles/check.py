import cloup as click
import functools
from ofscraper.utils.args.parse.arguments.check import (
    force,
    text_only_option,
    text_option,
    check_mode_media_sort,
)
from ofscraper.utils.args.parse.arguments.metadata_filters import (
    downloaded_option,
    lock_option,
    check_media_id_filter_option,
    check_post_id_filter_option,
)

from ofscraper.utils.args.parse.groups.media_filter import (
    length_max,
    length_min,
    media_type_option,
    quality_option,
    media_desc_option,
    max_size_option,
    min_size_option,
)

from ofscraper.utils.args.parse.groups.download import download_options
from ofscraper.utils.args.parse.groups.file import file_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.program import program_options
from ofscraper.utils.args.parse.arguments.metadata_filters import (
    posted_after,
    posted_before,
)
from ofscraper.utils.args.parse.arguments.post_content import (
    download_type_option
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


def common_args_check(func):
    @program_options
    @logging_options
    @download_options
    @click.option_group(
        "Download Filter Options",
        quality_option,
        help="options for selecting which media is downloaded",
    )
    @click.option_group(
        "Table Filter Options",
        media_type_option,
        check_mode_media_sort,
        length_max,
        length_min,
        lock_option,
        downloaded_option,
        check_media_id_filter_option,
        check_post_id_filter_option,
        media_desc_option,
        posted_after,
        posted_before,
        download_type_option,
        help="Filters for controlling the initial table view",
    )
    @click.option_group(
        "Download Filter Options",
        min_size_option,
        max_size_option,
        help="Filters for controlling which media to download",
    )
    @file_options
    @functools.wraps(func)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
