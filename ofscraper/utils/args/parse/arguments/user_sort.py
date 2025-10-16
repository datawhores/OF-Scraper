import cloup as click

sort_by_option = click.option(
    "-st",
    "--sort",
    help="What to sort the model list by",
    default="Name",
    type=click.Choice(
        [
            "name",
            "subscribed",
            "expired",
            "current-price",
            "renewal-price",
            "regular-price",
            "promo-price",
            "last-seen",
        ],
        case_sensitive=False,
    ),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

sort_descending_option = click.option(
    "-ds",
    "--desc",
    help="Sort the model list in descending order",
    is_flag=True,
    default=False,
)
