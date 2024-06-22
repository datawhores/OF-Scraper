import cloup as click
from ofscraper.utils.args.parse.arguments.advanced_user_filter import promo_price_max_option,promo_price_min_option,regular_price_max_option,regular_price_min_option,current_price_max_option,current_price_min_option,renewal_price_max_option,renewal_price_min_option,last_seen_after_option,last_seen_before_option,expired_after_option,expired_before_option,subscribed_after_option,subscribed_before_option
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
