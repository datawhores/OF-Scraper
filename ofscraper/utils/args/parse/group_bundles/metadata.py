import cloup as click
from click.exceptions import UsageError

from ofscraper.utils.const import METADATA_OPTIONS
from ofscraper.utils.args.parse.groups.advanced_processing import (
    advanced_processing_options,
)
from ofscraper.utils.args.parse.groups.advanced_user_filter import (
    advanced_userfilters_options,
)
from ofscraper.utils.args.parse.groups.file import file_options
from ofscraper.utils.args.parse.groups.logging import logging_options
from ofscraper.utils.args.parse.groups.program import program_options
from ofscraper.utils.args.parse.groups.user_list import userlist_options
from ofscraper.utils.args.parse.groups.user_select import user_select_options
from ofscraper.utils.args.parse.groups.user_sort import user_sorting_options
from ofscraper.utils.args.parse.groups.download import (
    download_options_help,
    download_options_tuple,
)
from ofscraper.utils.args.parse.groups.advanced_program import advanced_options
from ofscraper.utils.args.parse.groups.media_filter import media_filter_options

from ofscraper.utils.args.parse.groups.post_filter import (
    filter_option,
    label_option,
    mass_msg_option,
    neg_filter_option,
    posts_option,
    timed_only_option,
    post_id_filter_option,
    post_sort_option,
    post_filter_options_desc,
    post_filter_options_help,
)


from ofscraper.utils.args.helpers.hide_args import hide_metadata_mode


def metadata_args(func):
    @click.command(
        "metadata",
        short_help=" Modify metadata or db files",
        help="""
Uses API to modify db files without the need for downloading
""",
        show_constraints=True,
    )
    @click.option_group(
        "metadata_options",
        click.option(
            "-md",
            "--metadata",
            "metadata",
            help="""
        \b\n
METADATA MODES\n
check:\n
Updates metadata fields for the specified area via an API\n
This option does not check for new filenames\n
update: This mode performs two actions:\n
1. Updates download status and filenames based on the presence of actual files\n
2. Updates metadata fields for the specified area via an API\n
complete: \n
Marks the download as complete and updates metadata fields via an API\n
It also uses a new filename if one is available
        """,
            type=click.Choice(METADATA_OPTIONS),
            metavar="METADATA MODE",
        ),
        click.option(
            "-ms",
            "--mark-stray-locked",
            "--mark-stray",
            "mark_stray",
            help="""
        \b
        Sets unmatched media items as locked
        This is done per api type excluding labels, 
        and is limited to --after and --before range
        """,
            flag_value=True,
            is_flag=True,
        ),
        click.option(
            "-an",
            "--anon",
            "anon",
            help="""
        \b
        Use anonymise creditional
        forces --individual flag
        force --list flag to be removed
        most media is ignored
        """,
            flag_value=True,
            is_flag=True,
        ),
    )
    @program_options
    @logging_options
    @media_filter_options
    @file_options
    @click.option_group(
        post_filter_options_desc,
        click.option(
            "-sp",
            "--scrape-paid",
            help="Similar to --metadata, but only for --scrape paid",
            metavar="METADATA MODE",
            type=click.Choice(METADATA_OPTIONS),
        ),
        posts_option,
        label_option,
        filter_option,
        neg_filter_option,
        post_sort_option,
        timed_only_option,
        mass_msg_option,
        post_id_filter_option,
        help=post_filter_options_help,
    )
    @click.option_group(
        "Metadata Options", *download_options_tuple, help=download_options_help
    )
    @user_select_options
    @userlist_options
    @advanced_userfilters_options
    @user_sorting_options
    @advanced_processing_options
    @advanced_options
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        if ctx.params["anon"]:
            if not ctx.params["usernames"]:
                raise UsageError("'--usernames is required")
            elif len(list(filter(lambda x: x != "ALL", ctx.params["usernames"]))) == 0:
                raise UsageError("'--usernames value 'ALL' ignored is required")
            else:
                ctx.params["individual"] = True
                ctx.params["list"] = False
        elif not ctx.params["metadata"] and not ctx.params["scrape_paid"]:
            raise UsageError("'--scrape-paid' and/or --metadata is required")
        ctx.params["action"] = []
        return func(ctx, *args, **kwargs)

    hide_metadata_mode(wrapper)
    return wrapper
