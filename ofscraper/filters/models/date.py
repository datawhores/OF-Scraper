"""
date filters
"""

import logging

import arrow

import ofscraper.utils.args.read as read_args


def dateFilters(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Last Seen After Filter: {read_args.retriveArgs().last_seen_after}")
    if read_args.retriveArgs().last_seen_after:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen >= read_args.retriveArgs().last_seen_after,
                filterusername,
            )
        )
        log.debug(f"last seen after username count: {len(filterusername)}")
    log.debug(f"Last Seen Before Filter: {read_args.retriveArgs().last_seen_before}")
    if read_args.retriveArgs().last_seen_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= read_args.retriveArgs().last_seen_before,
                filterusername,
            )
        )
        log.debug(f"last seen before username count: {len(filterusername)}")

    log.debug(f"Subscribed After Filter: {read_args.retriveArgs().subscribed_after}")
    if read_args.retriveArgs().subscribed_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.subscribed)
                >= read_args.retriveArgs().subscribed_after,
                filterusername,
            )
        )
        log.debug(f"subscribed after username count: {len(filterusername)}")
    log.debug(f"Subscribed Before Filter: {read_args.retriveArgs().subscribed_before}")
    if read_args.retriveArgs().subscribed_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen
                <= read_args.retriveArgs().subscribed_before,
                filterusername,
            )
        )
        log.debug(f"subscribed before username count: {len(filterusername)}")
    log.debug(f"Expired After Filter: {read_args.retriveArgs().expired_after}")
    if read_args.retriveArgs().expired_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) >= read_args.retriveArgs().expired_after,
                filterusername,
            )
        )
        log.debug(f"expired after username count: {len(filterusername)}")
    log.debug(f"Expired Before Filter: {read_args.retriveArgs().expired_before}")
    if read_args.retriveArgs().expired_before:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired)
                <= read_args.retriveArgs().expired_before,
                filterusername,
            )
        )
        log.debug(f"expired before username count: {len(filterusername)}")
    return filterusername
