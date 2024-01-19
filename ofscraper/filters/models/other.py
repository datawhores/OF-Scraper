"""
other filters
"""

import logging

import ofscraper.utils.args.globals as global_args


def otherFilters(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Excluded usernames: {global_args.getArgs().excluded_username}")
    if len(global_args.getArgs().excluded_username) > 0:
        filterusername = list(
            filter(
                lambda x: x.name not in global_args.getArgs().excluded_username,
                filterusername,
            )
        )
        log.debug(f"excluded username count: {len(filterusername)}")

    return filterusername
