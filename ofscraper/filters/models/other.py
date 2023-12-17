"""
other filters
"""

import logging

import ofscraper.utils.args as args_


def otherFilters(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Excluded usernames: {args_.getargs().excluded_username}")
    if len(args_.getargs().excluded_username) > 0:
        filterusername = list(
            filter(
                lambda x: x.name not in args_.getargs().excluded_username,
                filterusername,
            )
        )
        log.debug(f"excluded username count: {len(filterusername)}")

    return filterusername
