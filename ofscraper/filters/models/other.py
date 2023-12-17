"""
other filters
"""

import logging

import ofscraper.utils.args as args_


def otherFilters(filterusername):
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
        log.debug(f"last seen befpre username count: {len(filterusername)}")
    log.debug(f"Excluded usernames: {args_.getargs().excluded_username}")
    if len(args_.getargs().excluded_username) > 0:
        filterusername = list(
            filter(
                lambda x: x.name not in args_.getargs().excluded_username,
                filterusername,
            )
        )

    return filterusername
