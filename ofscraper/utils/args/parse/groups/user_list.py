import cloup as click
from ofscraper.utils.args.parse.arguments.user_list import current_price_option,renewal_option,regular_price_option,free_trial_option,renewal_price_option,promo_option,last_seen_option,promo_price_option,all_promo_option,sub_status_option
# Create the option group
userlist_options = click.option_group(
    "User List Filter Options",
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
    help="Filter users with options like price (current/renewal/regular/promo), free trial, promo availability, alongside userlist filters (include/exclude)",
)