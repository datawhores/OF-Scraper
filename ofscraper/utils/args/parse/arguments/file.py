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
    help="set length based on word or letter",
    type=click.Choice(["word", "letter"], case_sensitive=False),
    default="word",
)

space_replacer_option = click.option(
    "-sr",
    "--space-replacer",
    help="character to replace spaces with",
)

text_length_option = click.option(
    "-tl", "--textlength", help="max length of text", type=click.INT
)
