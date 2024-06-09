import logging

import ofscraper.utils.args.accessors.read as read_args


def sort_models_helper(models):
    sort = read_args.retriveArgs().sort
    reverse = read_args.retriveArgs().desc
    logging.getLogger("shared").debug(
        f"sorting details  [name:{sort} direction:{reverse}]"
    )
    if sort == "name":
        return sorted(models, reverse=reverse, key=lambda x: x.name)

    elif sort == "last-seen":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x.final_last_seen,
        )
    elif sort == "expired":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x.final_expired,
        )
    elif sort == "subscribed":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x.final_subscribed,
        )
    elif sort == "current-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x.final_current_price,
        )
    elif sort == "promo-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x.final_promo_price,
        )

    elif sort == "renewal-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x.final_renewal_price,
        )

    elif sort == "regular-price":
        return sorted(models, reverse=reverse, key=lambda x: x.final_regular_price)
    else:
        return sorted(models, reverse=reverse, key=lambda x: x.name)
