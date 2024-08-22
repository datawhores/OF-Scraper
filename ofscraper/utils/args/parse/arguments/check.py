# checkmode  args
import cloup as click

from ofscraper.utils.args.callbacks.file import FileCallback
from ofscraper.utils.args.callbacks.string import (
    StringSplitParse,
    StringSplitParseTitle,
)
from ofscraper.utils.args.types.choice import MultiChoice

check_areas = click.option(
    "-ca",
    "--check-area",
    "--post",
    "--posts",
    "check_area",
    help="Select areas to check (multiple allowed, separated by spaces)",
    default=["Timeline", "Pinned", "Archived", "Streams"],
    type=MultiChoice(
        ["All", "Archived", "Timeline", "Pinned", "Labels", "Streams"],
        case_sensitive=False,
    ),
    callback=StringSplitParseTitle,
    multiple=True,
)


url_option = click.option(
    "-u",
    "--url",
    help="Scan posts via space or comma seperated list of urls",
    default=None,
    multiple=True,
    callback=StringSplitParse,
)
file_option = click.option(
    "-f",
    "--file",
    help="Scan posts via a file with line-separated URL(s)",
    default=None,
    type=click.File(),
    multiple=True,
    callback=FileCallback,
)


file_username_option = click.option(
    "-f",
    "--file",
    help="Scan posts via a file with line-separated URL(s)",
    default=None,
    type=lambda x: click.File(),
    multiple=True,
    callback=FileCallback,
)
user_option = click.option(
    "-u",
    "--usernames",
    "--username",
    "check_usernames",
    help="Scan stories/highlights via username(s)",
    default=None,
    multiple=True,
    callback=StringSplitParse,
)
force = click.option(
    "-fo",
    "--force",
    help="Force retrieval of new posts info from API",
    is_flag=True,
    default=False,
)

text_only_option = click.option(
    "-tp",
    "--text-only",
    "--download-text-only",
    "text_only",
    help="""
    Download Text files, but skip download media
    """,
    default=False,
    is_flag=True,
)

text_option = click.option(
    "-tn",
    "--text",
    "--download-text",
    "text_only",
    help="""
    Download Text files in addition to media
    """,
    default=False,
    is_flag=True,
)
