import logging

import ofscraper.utils.args as args_


def promoFilterHelper(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Promo Price: {args_.getargs().promo}")
    if args_.getargs().promo == "yes":
        filterusername = list(
            filter(lambda x: x.get("promo-price") is not None, filterusername)
        )
    elif args_.getargs().promo == "no":
        filterusername = list(
            filter(lambda x: x.get("promo-price") is None, filterusername)
        )
    log.debug(f"All Promo Price: {args_.getargs().all_promo}")
    if args_.getargs().all_promo == "yes":
        filterusername = list(
            filter(lambda x: x.get("all-promo-price") is not None, filterusername)
        )
    elif args_.getargs().all_promo == "no":
        filterusername = list(
            filter(lambda x: x.get("all-promo-price") is None, filterusername)
        )
    return filterusername
