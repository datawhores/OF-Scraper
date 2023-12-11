import logging

import ofscraper.utils.args as args_


def promoFilterHelper(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Promo Flag: {args_.getargs().promo}")
    if args_.getargs().promo == "yes":
        filterusername = list(
            filter(lambda x: x.lowest_promo_claim is not None, filterusername)
        )
        log.debug(f"Promo Flag Yes Count: {len(filterusername)}")

    elif args_.getargs().promo == "no":
        filterusername = list(
            filter(lambda x: x.lowest_promo_claim is None, filterusername)
        )
        log.debug(f"Promo Flag No Count: {len(filterusername)}")

    log.debug(f"All Promo Flag: {args_.getargs().all_promo}")
    if args_.getargs().all_promo == "yes":
        filterusername = list(
            filter(lambda x: x.lowest_promo_all is not None, filterusername)
        )
        log.debug(f"All Promo Flag Yes Count: {len(filterusername)}")

    elif args_.getargs().all_promo == "no":
        filterusername = list(
            filter(lambda x: x.lowest_promo_all is None, filterusername)
        )
        log.debug(f"All Promo Flag No Count: {len(filterusername)}")

    return filterusername
