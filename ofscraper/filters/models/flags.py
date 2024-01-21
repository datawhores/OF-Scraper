import logging

import ofscraper.utils.args.read as read_args


def promoFilterHelper(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Promo Flag: {read_args.retriveArgs().promo}")
    if read_args.retriveArgs().promo:
        filterusername = list(
            filter(lambda x: x.lowest_promo_claim is not None, filterusername)
        )
        log.debug(f"Promo Flag Yes Count: {len(filterusername)}")

    elif read_args.retriveArgs().promo is False:
        filterusername = list(
            filter(lambda x: x.lowest_promo_claim is None, filterusername)
        )
        log.debug(f"Promo Flag No Count: {len(filterusername)}")

    log.debug(f"All Promo Flag: {read_args.retriveArgs().all_promo}")
    if read_args.retriveArgs().all_promo:
        filterusername = list(
            filter(lambda x: x.lowest_promo_all is not None, filterusername)
        )
        log.debug(f"All Promo Flag Yes Count: {len(filterusername)}")

    elif read_args.retriveArgs().all_promo is False:
        filterusername = list(
            filter(lambda x: x.lowest_promo_all is None, filterusername)
        )
        log.debug(f"All Promo Flag No Count: {len(filterusername)}")
    log.debug(f"Last Seen Flag: {read_args.retriveArgs().last_seen}")
    if read_args.retriveArgs().last_seen:
        filterusername = list(filter(lambda x: x.last_seen is not None, filterusername))
        log.debug(f"Last Seen Flag Yes Count: {len(filterusername)}")

    elif read_args.retriveArgs().last_seen is False:
        filterusername = list(filter(lambda x: x.last_seen is None, filterusername))
        log.debug(f"Last Seen Flag No Count: {len(filterusername)}")
        log.debug(f"Last Seen Flag: {read_args.retriveArgs().last_seen}")
    if read_args.retriveArgs().free_trial:
        filterusername = list(
            filter(
                lambda x: (
                    (x.final_current_price == 0 or x.final_promo_price == 0)
                    and x.final_regular_price > 0
                ),
                filterusername,
            )
        )
        log.debug(f"Free Trial Flag Yes Count: {len(filterusername)}")

    elif read_args.retriveArgs().free_trial is False:
        filterusername = list(
            filter(
                lambda x: (x.final_current_price > 0 or x.final_regular_price == 0),
                filterusername,
            )
        )
        log.debug(f"Free Trial Flag No Count: {len(filterusername)}")
    return filterusername
