"""
date filters
"""

import logging

import arrow

import ofscraper.utils.args.globals as global_args


def dateFilters(filterusername):
    log = logging.getLogger("shared")

    log.debug(f"Last Seen After Filter: {global_args.getArgs().last_seen_after}")
    if global_args.getArgs().last_seen_after:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen >= global_args.getArgs().last_seen_after,
                filterusername,
            )
        )
        log.debug(f"last seen after username count: {len(filterusername)}")
    log.debug(f"Last Seen Before Filter: {global_args.getArgs().last_seen_before}")
    if global_args.getArgs().last_seen_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= global_args.getArgs().last_seen_before,
                filterusername,
            )
        )
        log.debug(f"last seen before username count: {len(filterusername)}")

    log.debug(f"Subscribed After Filter: {global_args.getArgs().subscribed_after}")
    if global_args.getArgs().subscribed_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.subscribed)
                >= global_args.getArgs().subscribed_after,
                filterusername,
            )
        )
        log.debug(f"subscribed after username count: {len(filterusername)}")
    log.debug(f"Subscribed Before Filter: {global_args.getArgs().subscribed_before}")
    if global_args.getArgs().subscribed_before:
        filterusername = list(
            filter(
                lambda x: x.final_last_seen <= global_args.getArgs().subscribed_before,
                filterusername,
            )
        )
        log.debug(f"subscribed before username count: {len(filterusername)}")
    log.debug(f"Expired After Filter: {global_args.getArgs().expired_after}")
    if global_args.getArgs().expired_after:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) >= global_args.getArgs().expired_after,
                filterusername,
            )
        )
        log.debug(f"expired after username count: {len(filterusername)}")
    log.debug(f"Expired Before Filter: {global_args.getArgs().expired_before}")
    if global_args.getArgs().expired_before:
        filterusername = list(
            filter(
                lambda x: arrow.get(x.expired) <= global_args.getArgs().expired_before,
                filterusername,
            )
        )
        log.debug(f"expired before username count: {len(filterusername)}")
    return filterusername
