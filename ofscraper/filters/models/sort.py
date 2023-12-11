import arrow

import ofscraper.utils.args as args_


def sort_models_helper(models):
    sort = args_.getargs().sort
    reverse = args_.getargs().desc
    if sort == "name":
        return sorted(models, reverse=reverse, key=lambda x: x["name"])
    elif sort == "expired":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: arrow.get(x.get("expired") or 0).float_timestamp,
        )
    elif sort == "subscribed":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: arrow.get(x.get("subscribed") or 0).float_timestamp,
        )
    elif sort == "current-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x["final-current-price"],
        )
    elif sort == "promo-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x["final-promo-price"],
        )

    elif sort == "renewal-price":
        return sorted(
            models,
            reverse=reverse,
            key=lambda x: x["final-renewal-price"],
        )

    elif sort == "regular-price":
        return sorted(models, reverse=reverse, key=lambda x: x["final-regular-price"])
    else:
        return sorted(models, reverse=reverse, key=lambda x: x["name"])
