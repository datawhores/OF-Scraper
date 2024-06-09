import re

import arrow
from InquirerPy.base import Choice

import ofscraper.utils.args.accessors.read as read_args


def model_selectorHelper(count, x):
    return Choice(
        x,
        name=f"{count+1}: {x.name}   =>  subscribed date: {generalDated(x.subscribed_string)}{renewHelper(x)}{lastSeenHelper(x)} | {getPriceHelper(x)}",
    )


def renewHelper(x):
    if (
        read_args.retriveArgs().sort != "expired"
        and read_args.retriveArgs().renewal is None
    ):
        return ""
    return (
        " | end/renewed date: N/A"
        if (x.renewed_string or x.expired_string) is None
        else f" | end/renewed date: {arrow.get(x.renewed_string or x.expired_string).format('YYYY-MM-DD: HH:mm')}"
    )


def generalDated(value):
    if value is None:
        return "N/A"
    return value


def lastSeenHelper(x):
    if (
        read_args.retriveArgs().sort != "last-seen"
        and not read_args.retriveArgs().last_seen
        and not read_args.retriveArgs().last_seen_after
        and not read_args.retriveArgs().last_seen_before
    ):
        return ""
    return (
        " | last seen: Hidden"
        if x.last_seen is None
        else f" | last seen: {arrow.get(x.last_seen).format('YYYY-MM-DD: HH:mm')}"
    )


def getPriceHelper(x):
    value = None
    value2 = None
    if read_args.retriveArgs().sort in {
        "current-price",
        "renewal-price",
        "regular-price",
        "promo-price",
    }:
        value = re.sub("-", "_", read_args.retriveArgs().sort).replace("-", "_")
    if (
        read_args.retriveArgs().promo_price
        or read_args.retriveArgs().promo_price_min
        or read_args.retriveArgs().promo_price_max
    ):
        value2 = "promo_price"
    elif (
        read_args.retriveArgs().regular_price
        or read_args.retriveArgs().regular_price_min
        or read_args.retriveArgs().regular_price_max
    ):
        value2 = "regular_price"
    elif (
        read_args.retriveArgs().renewal_price
        or read_args.retriveArgs().renewal_price_min
        or read_args.retriveArgs().renewal_price_max
    ):
        value2 = "renewal_price"
    elif (
        read_args.retriveArgs().current_price
        or read_args.retriveArgs().current_price_min
        or read_args.retriveArgs().current_price_max
    ):
        value2 = "current_price"
    final_value = value or value2 or "current_price"
    key = f"final_{final_value}"
    return f"{final_value }: {getattr(x, key)}"
