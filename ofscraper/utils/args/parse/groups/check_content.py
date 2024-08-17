import cloup as click

from ofscraper.utils.args.parse.arguments.check import (
    check_areas,
    url_option,
    file_option,
    user_option,
    file_username_option,
)
from ofscraper.utils.args.parse.arguments.content import timeline_strict

content_check_options_desc = "Content Options"
content_check_options_help = """
    \b
    Define what posts to target (areas, filters) and actions to perform (like, unlike, download)
    Filter by type, date, label, size, and media type"""
content_check_options_tuple = (timeline_strict, check_areas)


content_check_options = click.option_group(
    content_check_options_desc,
    *content_check_options_tuple,
    help=content_check_options_help,
)


url_group = click.constraints.require_one(url_option, file_option)

username_group = click.constraints.require_one(user_option, file_username_option)
