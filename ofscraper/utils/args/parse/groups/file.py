import cloup as click
from ofscraper.utils.args.parse.arguments.file import original_filename_option,text_length_option,text_type_option,space_replacer_option
# Create the option group with help text
file_options = click.option_group(
    "Filename Modification Options",
    original_filename_option,
    text_type_option,
    space_replacer_option,
    text_length_option,
    help="""
\b
Options for controlling the output of the final filename after placeholders are replaced
""",
)