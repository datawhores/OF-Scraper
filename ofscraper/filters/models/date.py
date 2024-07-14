"""
date filters
"""

import logging

import arrow

import ofscraper.utils.args.accessors.read as read_args
from ofscraper.filters.models.utils.logs import trace_log_user


def dateFilters(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Last seen after filter: {read_args.retriveArgs().last_seen_after}")
    if read_args.retriveArgs().last_seen_after:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen >= read_args.retriveArgs().last_seen_after,
                filterusername,
            )
        )
        log.debug(f"Last seen after filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "last seen after")
    log.debug(f"Last seen before filter: {read_args.retriveArgs().last_seen_before}")
    if read_args.retriveArgs().last_seen_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= read_args.retriveArgs().last_seen_before,
                filterusername,
            )
        )
        log.debug(f"last seen before filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "last seen before")

    log.debug(f"Subscribed after filter: {read_args.retriveArgs().subscribed_after}")
    if read_args.retriveArgs().subscribed_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.subscribed)
                >= read_args.retriveArgs().subscribed_after,
                filterusername,
            )
        )
        log.debug(f"subscribed after filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "subscribed after")

    log.debug(f"Subscribed before filter: {read_args.retriveArgs().subscribed_before}")
    if read_args.retriveArgs().subscribed_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen
                <= read_args.retriveArgs().subscribed_before,
                filterusername,
            )
        )
        log.debug(f"subscribed before filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "Subscribed before")

    log.debug(f"Expired After Filter: {read_args.retriveArgs().expired_after}")
    if read_args.retriveArgs().expired_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) >= read_args.retriveArgs().expired_after,
                filterusername,
            )
        )
        log.debug(f"expired after filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "expired after")

    log.debug(f"Expired Before Filter: {read_args.retriveArgs().expired_before}")
    if read_args.retriveArgs().expired_before:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired)
                <= read_args.retriveArgs().expired_before,
                filterusername,
            )
        )
        log.debug(f"expired before filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "expired before")
    return filterusername
