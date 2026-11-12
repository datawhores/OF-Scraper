import re

import arrow
from InquirerPy.base import Choice
from rich.cells import cell_len
import ofscraper.utils.settings as settings


def model_selector_choices(models):
    models = list(models)
    rows = [
        [
            str(count + 1),
            x.name,
            f"subscribed date: {generalDated(x.subscribed_string)}",
            renewHelper(x).removeprefix(" | "),
            lastSeenHelper(x).removeprefix(" | "),
            getPriceHelper(x),
        ]
        for count, x in enumerate(models)
    ]
    widths = [max(map(cell_len, column)) for column in zip(*rows)]
    choices = []
    for x, row in zip(models, rows):
        padded = [
            value + " " * (width - cell_len(value))
            for value, width in zip(row, widths)
        ]
        number = row[0].rjust(widths[0])
        details = " | ".join(value for value in padded[2:] if value)
        choices.append(Choice(x, name=f"{number}: {padded[1]}   =>  {details}"))
    return choices


def renewHelper(x):
    if (
        settings.get_settings().sort != "expired"
        and settings.get_settings().renewal is None
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
        settings.get_settings().sort != "last-seen"
        and not settings.get_settings().last_seen
        and not settings.get_settings().last_seen_after
        and not settings.get_settings().last_seen_before
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
    if settings.get_settings().sort in {
        "current-price",
        "renewal-price",
        "regular-price",
        "promo-price",
    }:
        value = re.sub("-", "_", settings.get_settings().sort).replace("-", "_")
    if (
        settings.get_settings().promo_price
        or settings.get_settings().promo_price_min
        or settings.get_settings().promo_price_max
    ):
        value2 = "promo_price"
    elif (
        settings.get_settings().regular_price
        or settings.get_settings().regular_price_min
        or settings.get_settings().regular_price_max
    ):
        value2 = "regular_price"
    elif (
        settings.get_settings().renewal_price
        or settings.get_settings().renewal_price_min
        or settings.get_settings().renewal_price_max
    ):
        value2 = "renewal_price"
    elif (
        settings.get_settings().current_price
        or settings.get_settings().current_price_min
        or settings.get_settings().current_price_max
    ):
        value2 = "current_price"
    final_value = value or value2 or "current_price"
    key = f"final_{final_value}"
    return f"{final_value }: {getattr(x, key)}"
