import logging

import ofscraper.utils.args as args_


def pricePaidFreeFilterHelper(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Current Price Filter: {args_.getargs().current_price}")
    if args_.getargs().current_price == "paid":
        filterusername = list(
            filter(
                lambda x: x["final-current-price"] > 0,
                filterusername,
            )
        )
        log.debug(f"currently paid filter username count: {len(filterusername)}")
    elif args_.getargs().current_price == "free":
        filterusername = list(
            filter(
                lambda x: x["final-current-price"] == 0,
                filterusername,
            )
        )
        log.debug(f"currently free filter username count: {len(filterusername)}")
    log.debug(f"Account Renewal Price Filter: {args_.getargs().renewal_price}")
    if args_.getargs().renewal_price == "paid":
        filterusername = list(
            filter(
                lambda x: x["final-renewal-price"] > 0,
                filterusername,
            ),
        )

        log.debug(f"paid renewal filter username count: {len(filterusername)}")
    elif args_.getargs().renewal_price == "free":
        filterusername = list(
            filter(
                lambda x: x["final-renewal-price"] == 0,
                filterusername,
            )
        )
        log.debug(f"free renewal filter username count: {len(filterusername)}")

    log.debug(f"Regular Price Filter: {args_.getargs().regular_price}")
    if args_.getargs().regular_price == "paid":
        filterusername = list(
            filter(lambda x: x["final-regular-price"], filterusername)
        )
        log.debug(f"paid regular price filter username count: {len(filterusername)}")
    elif args_.getargs().regular_price == "free":
        filterusername = list(
            filter(lambda x: x["final-regular-price"]), filterusername
        )
        log.debug(f"free regular price filter username count: {len(filterusername)}")
    log.debug(f"Promo Price Filter: {args_.getargs().promo_price}")
    if args_.getargs().promo_price == "paid":
        filterusername = list(
            filter(
                lambda x: x["final-promo-price"] > 0,
                filterusername,
            )
        )

        log.debug(f"paid promo filter username count: {len(filterusername)}")
    elif args_.getargs().promo_price == "free":
        filterusername = list(
            filter(
                lambda x: x["final-promo-price"] == 0,
                filterusername,
            )
        )
        log.debug(f"free promo filter username count: {len(filterusername)}")
    return filterusername
