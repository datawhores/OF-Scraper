"""
date filters
"""

import logging

import arrow

from ofscraper.filters.models.utils.logs import trace_log_user
import ofscraper.utils.settings as settings


def dateFilters(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Last seen after filter: {settings.get_settings().last_seen_after}")
    if settings.get_settings().last_seen_after:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen >= settings.get_settings().last_seen_after,
                filterusername,
            )
        )
        log.debug(f"Last seen after filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "last seen after")
    log.debug(f"Last seen before filter: {settings.get_settings().last_seen_before}")
    if settings.get_settings().last_seen_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= settings.get_settings().last_seen_before,
                filterusername,
            )
        )
        log.debug(f"last seen before filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "last seen before")

    log.debug(f"Subscribed after filter: {settings.get_settings().subscribed_after}")
    if settings.get_settings().subscribed_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.subscribed)
                >= settings.get_settings().subscribed_after,
                filterusername,
            )
        )
        log.debug(f"subscribed after filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "subscribed after")

    log.debug(f"Subscribed before filter: {settings.get_settings().subscribed_before}")
    if settings.get_settings().subscribed_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen
                <= settings.get_settings().subscribed_before,
                filterusername,
            )
        )
        log.debug(f"subscribed before filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "Subscribed before")

    log.debug(f"Expired After Filter: {settings.get_settings().expired_after}")
    if settings.get_settings().expired_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) >= settings.get_settings().expired_after,
                filterusername,
            )
        )
        log.debug(f"expired after filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "expired after")

    log.debug(f"Expired Before Filter: {settings.get_settings().expired_before}")
    if settings.get_settings().expired_before:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired)
                <= settings.get_settings().expired_before,
                filterusername,
            )
        )
        log.debug(f"expired before filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "expired before")
    return filterusername
