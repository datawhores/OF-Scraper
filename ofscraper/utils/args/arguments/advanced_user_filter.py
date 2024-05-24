import cloup as click

import ofscraper.utils.args.helpers.type as type

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
    callback=lambda ctx, param, value: (type.arrow_helper(value) if value else None),
)

last_seen_after_option = click.option(
    "-lsa",
    "--last-seen-after",
    help="Filter accounts by last seen being at or after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: (type.arrow_helper(value) if value else None),
)

expired_after_option = click.option(
    "-ea",
    "--expired-after",
    help="Filter accounts by expiration/renewal being at or after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: (type.arrow_helper(value) if value else None),
)

expired_before_option = click.option(
    "-eb",
    "--expired-before",
    help="Filter accounts by expiration/renewal being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: (type.arrow_helper(value) if value else None),
)

subscribed_after_option = click.option(
    "-sa",
    "--subscribed-after",
    help="Filter accounts by subscription date being after the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: (type.arrow_helper(value) if value else None),
)

subscribed_before_option = click.option(
    "-sb",
    "--subscribed-before",
    help="Filter accounts by sub date being at or before the given date (YYYY-MM-DD format)",
    default=None,
    required=False,
    callback=lambda ctx, param, value: (type.arrow_helper(value) if value else None),
)

# Create the option group

advanced_userfilters_options = click.option_group(
    "Advanced User List Filter Options",
    promo_price_min_option,
    promo_price_max_option,
    regular_price_min_option,
    regular_price_max_option,
    current_price_min_option,
    current_price_max_option,
    renewal_price_min_option,
    renewal_price_max_option,
    last_seen_before_option,
    last_seen_after_option,
    expired_after_option,
    expired_before_option,
    subscribed_after_option,
    subscribed_before_option,
    help="Precise user filtering with price ranges (current/renewal/regular/promo), last seen dates, expiration dates, and subscription dates",
)
