import cloup as click

current_price_option = click.option(
    "-cp",
    "--current-price",
    help="Filter accounts based on either the subscription price, lowest claimable promotional price, or regular price",
    default=None,
    required=False,
    type=click.Choice(["paid", "free"], case_sensitive=False),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

renewal_price_option = click.option(
    "-rp",
    "--renewal-price",
    help="Filter accounts based on either the lowest claimable promotional price, or regular price",
    default=None,
    required=False,
    type=click.Choice(["paid", "free"], case_sensitive=False),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

regular_price_option = click.option(
    "-gp",
    "--regular-price",
    help="Filter accounts based on the regular price",
    default=None,
    required=False,
    type=click.Choice(["paid", "free"], case_sensitive=False),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

promo_price_option = click.option(
    "-pp",
    "--promo-price",
    help="Filter accounts based on either the lowest promotional price regardless of claimability, or regular price",
    default=None,
    required=False,
    type=click.Choice(["paid", "free"], case_sensitive=False),
    callback=lambda ctx, param, value: value.lower() if value else None,
)

last_seen_option = click.option(
    "-lo/-ls",
    "--last-seen-only/--last-seen-skip",
    "last_seen",
    help="""
        \b
        Flag for filtering accounts based on last seen being visible
        [select one --last-seen-only or --last-seen-skip]""",
    default=None,
    required=False,
    is_flag=True,
)

free_trial_option = click.option(
    "-fo/-fs",
    "--free-trial-only/--free-trial-skip",
    "free_trail",  # Positional argument for destination attribute
    help="""
    \b
    Flag for enabling/disabling accounts with free trial
    [must be normally paid]
    [select one --free-trial-only or --free-trial-skip]""",
    default=None,
    required=False,
    is_flag=True,
)

promo_option = click.option(
    "-po/-ps",
    "--promo-only/--promo-skip",
    "promo",
    help="""
    \b
    Flag for enabling/disabling accounts with a claimable promo price
    [select one --promo-only or --promo-skip]""",
    default=None,
    required=False,
    is_flag=True,
)

all_promo_option = click.option(
    "-ao",
    "--all-promo-only/--all-promo-skip",
    "all_promo",
    help="""
        \b
        Flag for enabling/disabling  accounts with any promo price
        [select one all-promo-only or --all-promo-skip]""",
    default=None,
    required=False,
    is_flag=True,
)

sub_status_option = click.option(
    "-ts/-es",
    "--active-subscription/--expired-subscription",
    "sub_status",
    help="""\b
    Flag for enabling/disabling  accounts with active or expired subscription
    [select one --active-subscription or --expired-subscription]""",
    default=None,
    required=False,
    is_flag=True,
)

renewal_option = click.option(
    "-ro/-rf",
    "--renew-on/--renew-off",
    "renewal",
    help="""
    \b
    Flag for enabling/disabling accounts set to renew renew flag on 
    [select one --renew-on or --renew-off]""",
    default=None,
    required=False,
    is_flag=True,
)
