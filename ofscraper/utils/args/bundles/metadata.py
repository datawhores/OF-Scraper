import cloup as click

from ofscraper.const.constants import METADATA_OPTIONS
from ofscraper.utils.args.arguments.advanced_processing import  advanced_processing_options
from ofscraper.utils.args.arguments.advanced_program import (
    download_script_option,
    dynamic_rules_option,
    no_api_cache_option,
    no_cache_option,
    update_profile_option,
)
from ofscraper.utils.args.arguments.advanced_user_filter import (
    advanced_userfilters_options,
)
from ofscraper.utils.args.arguments.content import (
    after_option,
    before_option,
    content_options,
    filter_option,
    label_option,
    mass_msg_option,
    max_count_option,
    neg_filter_option,
    posts_option,
    timed_only_option,
)
from ofscraper.utils.args.arguments.file import file_options
from ofscraper.utils.args.arguments.logging import logging_options
from ofscraper.utils.args.arguments.media_type import quality_option
from ofscraper.utils.args.arguments.program import program_options
from ofscraper.utils.args.arguments.user_list import userlist_options
from ofscraper.utils.args.arguments.user_select import user_select_options
from ofscraper.utils.args.arguments.user_sort import user_sorting_options


def metadata_args(func):
    @click.command(
        "metadata",
        short_help=" Modify metadata or db files",
        help="""
Uses API to modify db files without the need for downloading
""",
    )
    @click.option_group(
        "metadata_options",
        click.option(
            "-md",
            "--metadata",
            "metadata",
            help="""
        \b
        How should metadata be handled
        check: only update metadata fields via api
        update: update download status based on file presence, and update metadata fields via api
        complete: update download to true, and update metadata fields
        """,
            type=click.Choice(METADATA_OPTIONS),
            required=True,
        ),
    )
    @click.option_group(
        "filter_stray",
        click.option(
            "-ms",
            "--mark-stray-downloaded",
            "--mark-stray",
            "mark_stray",
            help="""
        \b
        Sets unmatched media items as downloaded
        This is done per api type excluding labels, 
        and is limited to --after and --before range
        """,
            flag_value=True,
            is_flag=True,
        ),
    )
    @program_options
    @logging_options
    @click.option_group(
        "Media Filter Options", quality_option, help="Options for controlling "
    )
    @file_options
    @click.option_group(
        "Content Options",
        posts_option,
        filter_option,
        neg_filter_option,
        max_count_option,
        label_option,
        before_option,
        after_option,
        mass_msg_option,
        timed_only_option,
        help="""
    \b
     Define what posts to target
    """,
    )
    @content_options
    @user_select_options
    @userlist_options
    @advanced_userfilters_options
    @user_sorting_options
    @advanced_processing_options
    @click.option_group(
        "Advanced Program Options",
        no_cache_option,
        no_api_cache_option,
        dynamic_rules_option,
        update_profile_option,
        download_script_option,
        help="Advanced control of program behavior",
    )
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return func(ctx, *args, **kwargs)

    return wrapper
