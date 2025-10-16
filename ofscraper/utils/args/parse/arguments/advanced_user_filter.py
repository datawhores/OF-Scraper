import cloup as click

from ofscraper.utils.args.types.arrow import ArrowType

promo_price_min_option = click.option(
    "-ppn",
    "--promo-price-min",
    help="Filter accounts where the lowest promo price matches or falls above the provided value",
    default=None,
    required=False,
    type=int,
)

promo_price_max_option = click.option(
    "-ppm",
    "--promo-price-max",
    help="Filter accounts where the lowest promo price matches or falls below the provided value",
    default=None,
    required=False,
    type=int,
)

regular_price_min_option = click.option(
    "-gpn",
    "--regular-price-min",
    help="Filter accounts where the regular price matches or falls above the provided value",
    default=None,
    required=False,
    type=int,
)

regular_price_max_option = click.option(
    "-gpm",
    "--regular-price-max",
    help="Filter accounts where the regular price matches or falls below the provided value",
    default=None,
    required=False,
    type=int,
)

current_price_min_option = click.option(
    "-cpn",
    "--current-price-min",
    help="Filter accounts where the current regular price matches or falls above the provided value",
    default=None,
    required=False,
    type=int,
)

current_price_max_option = click.option(
    "-cpm",
    "--current-price-max",
    help="Filter accounts where the current price matches or falls below the provided value",
    default=None,
    required=False,
    type=int,
)

renewal_price_min_option = click.option(
    "-rpn",
    "--renewal-price-min",
    help="Filter accounts where the renewal regular price matches or falls above the provided value",
    default=None,
    required=False,
    type=int,
)

renewal_price_max_option = click.option(
    "-rpm",
    "--renewal-price-max",
    help="Filter accounts where the renewal price matches or falls below the provided value",
    default=None,
    required=False,
    type=int,
)

last_seen_before_option = click.option(
    "-lsb",
    "--last-seen-before",
    help="Filter accounts by last seen being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    type=ArrowType(),
)

last_seen_after_option = click.option(
    "-lsa",
    "--last-seen-after",
    help="Filter accounts by last seen being at or after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    type=ArrowType(),
)

expired_after_option = click.option(
    "-ea",
    "--expired-after",
    help="Filter accounts by expiration/renewal being at or after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    type=ArrowType(),
)

expired_before_option = click.option(
    "-eb",
    "--expired-before",
    help="Filter accounts by expiration/renewal being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    type=ArrowType(),
)

subscribed_after_option = click.option(
    "-sa",
    "--subscribed-after",
    help="Filter accounts by subscription date being after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    type=ArrowType(),
)

subscribed_before_option = click.option(
    "-sb",
    "--subscribed-before",
    help="Filter accounts by sub date being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    type=ArrowType(),
)
