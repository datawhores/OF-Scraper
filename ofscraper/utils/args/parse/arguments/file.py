import cloup as click

original_filename_option = click.option(
    "-g",
    "--original",
    help="Don't truncate long paths",
    is_flag=True,
)

text_type_option = click.option(
    "-tt",
    "--text-type",
    help="Measure text length by word or letter",
    type=click.Choice(["word", "letter"], case_sensitive=False),
)

space_replacer_option = click.option(
    "-sr",
    "--space-replacer",
    help="Character to replace spaces with",
)

text_length_option = click.option(
    "-tl",
    "--textlength",
    help="Max length of text, in letters or words (see --text-type)",
    type=click.INT,
)
