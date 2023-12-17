import logging

import ofscraper.utils.args as args_


def pricePaidFreeFilterHelper(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Current Price Filter: {args_.getargs().current_price}")
    if args_.getargs().current_price == "paid":
        filterusername = list(
            filter(
                lambda x: x.final_current_price > 0,
                filterusername,
            )
        )
        log.debug(f"currently paid filter username count: {len(filterusername)}")
    elif args_.getargs().current_price == "free":
        filterusername = list(
            filter(
                lambda x: x.final_current_price == 0,
                filterusername,
            )
        )
        log.debug(f"currently free filter username count: {len(filterusername)}")
    log.debug(f"Account Renewal Price Filter: {args_.getargs().renewal_price}")
    if args_.getargs().renewal_price == "paid":
        filterusername = list(
            filter(
                lambda x: x.final_renewal_price > 0,
                filterusername,
            ),
        )

        log.debug(f"paid renewal filter username count: {len(filterusername)}")
    elif args_.getargs().renewal_price == "free":
        filterusername = list(
            filter(
                lambda x: x.final_renewal_price == 0,
                filterusername,
            )
        )
        log.debug(f"free renewal filter username count: {len(filterusername)}")

    log.debug(f"Regular Price Filter: {args_.getargs().regular_price}")
    if args_.getargs().regular_price == "paid":
        filterusername = list(filter(lambda x: x.final_regular_price, filterusername))
        log.debug(f"paid regular price filter username count: {len(filterusername)}")
    elif args_.getargs().regular_price == "free":
        filterusername = list(
            filter(lambda x: x.final_regular_price == 0, filterusername)
        )
        log.debug(f"free regular price filter username count: {len(filterusername)}")
    log.debug(f"Promo Price Filter: {args_.getargs().promo_price}")
    if args_.getargs().promo_price == "paid":
        filterusername = list(
            filter(
                lambda x: x.final_promo_price > 0,
                filterusername,
            )
        )

        log.debug(f"paid promo filter username count: {len(filterusername)}")
    elif args_.getargs().promo_price == "free":
        filterusername = list(
            filter(
                lambda x: x.final_promo_price == 0,
                filterusername,
            )
        )
        log.debug(f"free promo filter username count: {len(filterusername)}")
    filterusername = priceMinMaxFilters(filterusername)

    return filterusername


def priceMinMaxFilters(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Promo Price min Filter: {args_.getargs().promo_price_min}")
    if args_.getargs().promo_price_min:
        filterusername = list(
            filter(
                lambda x: x.final_promo_price >= args_.getargs().promo_price_min,
                filterusername,
            )
        )
        log.debug(f"currently promo min filter: {len(filterusername)}")
    log.debug(f"Promo Price max Filter: {args_.getargs().promo_price_max}")
    if args_.getargs().promo_price_max:
        filterusername = list(
            filter(
                lambda x: x.final_promo_price <= args_.getargs().promo_price_max,
                filterusername,
            )
        )
        log.debug(f"currently promo max filter: {len(filterusername)}")

    log.debug(f"Regular Price min Filter: {args_.getargs().regular_price_min}")
    if args_.getargs().regular_price_min:
        filterusername = list(
            filter(
                lambda x: x.final_regular_price >= args_.getargs().regular_price_min,
                filterusername,
            )
        )
        log.debug(f"currently regular min filter: {len(filterusername)}")
    log.debug(f"Regular Price max Filter: {args_.getargs().regular_price_max}")
    if args_.getargs().regular_price_max:
        filterusername = list(
            filter(
                lambda x: x.final_regular_price <= args_.getargs().regular_price_max,
                filterusername,
            )
        )
        log.debug(f"currently regular max filter: {len(filterusername)}")

    log.debug(f"Renewal Price min Filter: {args_.getargs().renewal_price_min}")
    if args_.getargs().renewal_price_min:
        filterusername = list(
            filter(
                lambda x: x.final_renewal_price >= args_.getargs().renewal_price_min,
                filterusername,
            )
        )
        log.debug(f"currently renewal min filter: {len(filterusername)}")
    log.debug(f"Renewal Price max Filter: {args_.getargs().renewal_price_max}")
    if args_.getargs().renewal_price_max:
        filterusername = list(
            filter(
                lambda x: x.final_renewal_price <= args_.getargs().renewal_price_max,
                filterusername,
            )
        )
        log.debug(f"currently renewal max filter: {len(filterusername)}")

    log.debug(f"Current Price min Filter: {args_.getargs().current_price_min}")
    if args_.getargs().current_price_min:
        filterusername = list(
            filter(
                lambda x: x.final_current_price >= args_.getargs().current_price_min,
                filterusername,
            )
        )
        log.debug(f"currently current min filter: {len(filterusername)}")
    log.debug(f"Current Price max Filter: {args_.getargs().current_price_max}")
    if args_.getargs().current_price_max:
        filterusername = list(
            filter(
                lambda x: x.final_current_price <= args_.getargs().current_price_max,
                filterusername,
            )
        )
        log.debug(f"currently current max filter: {len(filterusername)}")
    return filterusername
