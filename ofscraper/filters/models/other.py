"""
other filters
"""

import logging

import ofscraper.utils.args.accessors.read as read_args
from ofscraper.filters.models.utils.logs import trace_log_user


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
        log.debug(f"'excluded usernames' filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "Excluded usernames")

    return filterusername
