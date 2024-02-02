"""
other filters
"""

import logging

import ofscraper.utils.args.read as read_args


def otherFilters(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Excluded usernames: {read_args.retriveArgs().excluded_username}")
    if len(read_args.retriveArgs().excluded_username) > 0:
        filterusername = list(
            filter(
                lambda x: x.name not in read_args.retriveArgs().excluded_username,
                filterusername,
            )
        )
        log.debug(f"excluded username count: {len(filterusername)}")

    return filterusername
