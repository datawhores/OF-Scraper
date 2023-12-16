import re

import arrow
from InquirerPy.base import Choice

import ofscraper.utils.args as args_


def model_selectorHelper(count, x):
    return Choice(
        x,
        name=f"{count+1}: {x.name}   =>  subscribed date: {generalDated(x.subscribed)}{renewHelper(x)}{lastSeenHelper(x)} | {getPriceHelper(x)}",
    )


def renewHelper(x):
    if args_.getargs().sort != "expired":
        return ""
    return (
        " | end/renewed date: N/A"
        if x.renewed or x.expired is None
        else f" | end/renewed date: {arrow.get(x.renewed or x.expired).format('YYYY-MM-DD: HH:mm')}"
    )


def generalDated(value):
    if value is None:
        return "N/A"
    return arrow.get(value).format("YYYY-MM-DD: HH:mm")


def lastSeenHelper(x):
    if args_.getargs().sort != "last-seen":
        return ""
    return (
        " | last seen: Hidden"
        if x.last_seen is None
        else f" | last seen: {arrow.get(x.last_seen).format('YYYY-MM-DD: HH:mm')}"
    )


def getPriceHelper(x):
    value = re.sub(
        "-",
        "_",
        args_.getargs().sort
        if args_.getargs().sort
        in {"current-price", "renewal-price", "regular-price", "promo-price"}
        else "current-price",
    ).replace("-", "_")
    key = f"final_{value}"
    return f"{value}: {getattr(x, key)}"
