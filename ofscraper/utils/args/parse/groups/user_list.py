import cloup as click

from ofscraper.utils.args.parse.arguments.user_list import (
    all_promo_option,
    current_price_option,
    free_trial_option,
    last_seen_option,
    promo_option,
    promo_price_option,
    regular_price_option,
    renewal_option,
    renewal_price_option,
    sub_status_option,
)

userlist_options_desc = "User List Filter Options"
userlist_options_help = "Filter users with options like price (current/renewal/regular/promo), free trial, promo availability, alongside userlist filters (include/exclude)"
userlist_options_tuple = (
    current_price_option,
    renewal_price_option,
    regular_price_option,
    promo_price_option,
    last_seen_option,
    free_trial_option,
    promo_option,
    all_promo_option,
    sub_status_option,
    renewal_option,
)
# Create the option group
userlist_options = click.option_group(
    userlist_options_desc,
    *userlist_options_tuple,
    help=userlist_options_help,
)
