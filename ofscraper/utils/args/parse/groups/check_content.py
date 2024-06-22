
import cloup as click
from ofscraper.utils.args.parse.arguments.content import timeline_strict
from ofscraper.utils.args.parse.arguments.check import check_areas
content_options = click.option_group(
    "Content Options",
    timeline_strict,
    check_areas,
    help="""
    \b
    Define what posts to target (areas, filters) and actions to perform (like, unlike, download)
    Filter by type, date, label, size, and media type""",
)