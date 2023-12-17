"""
date filters
"""

import logging

import arrow

import ofscraper.utils.args as args_


def dateFilters(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Last Seen After Filter: {args_.getargs().last_seen_after}")
    if args_.getargs().last_seen_after:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen >= args_.getargs().last_seen_after,
                filterusername,
            )
        )
        log.debug(f"last seen after username count: {len(filterusername)}")
    log.debug(f"Last Seen Before Filter: {args_.getargs().last_seen_before}")
    if args_.getargs().last_seen_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= args_.getargs().last_seen_before,
                filterusername,
            )
        )
        log.debug(f"last seen before username count: {len(filterusername)}")

    log.debug(f"Subscribed After Filter: {args_.getargs().subscribed_after}")
    if args_.getargs().subscribed_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.subscribed) >= args_.getargs().subscribed_after,
                filterusername,
            )
        )
        log.debug(f"subscribed after username count: {len(filterusername)}")
    log.debug(f"Subscribed Before Filter: {args_.getargs().subscribed_before}")
    if args_.getargs().subscribed_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= args_.getargs().subscribed_before,
                filterusername,
            )
        )
        log.debug(f"subscribed before username count: {len(filterusername)}")
    log.debug(f"Expired After Filter: {args_.getargs().expired_after}")
    if args_.getargs().expired_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) >= args_.getargs().expired_after,
                filterusername,
            )
        )
        log.debug(f"expired after username count: {len(filterusername)}")
    log.debug(f"Expired Before Filter: {args_.getargs().expired_before}")
    if args_.getargs().expired_before:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) <= args_.getargs().expired_before,
                filterusername,
            )
        )
        log.debug(f"expired before username count: {len(filterusername)}")
    return filterusername
