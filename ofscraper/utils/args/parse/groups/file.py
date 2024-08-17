import cloup as click

from ofscraper.utils.args.parse.arguments.file import (
    original_filename_option,
    space_replacer_option,
    text_length_option,
    text_type_option,
)


file_options_help = """
\b
Options for controlling the output of the final filename after placeholders are replaced
"""
file_options_desc = "Filename Modification Options"
# Create the option group with help text
file_options_tuple = (
    original_filename_option,
    space_replacer_option,
    text_length_option,
    text_type_option,
)

file_options = click.option_group(
    file_options_desc, *file_options_tuple, help=file_options_help
)
