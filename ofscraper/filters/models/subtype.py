import logging

import ofscraper.utils.args.accessors.read as read_args
from ofscraper.filters.models.utils.logs import trace_log_user


def subType(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Renewal: {read_args.retriveArgs().renewal}")
    if read_args.retriveArgs().renewal:
        filterusername = list(filter(lambda x: x.renewed, filterusername))
        log.debug(f"active renewal filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "active renewal filter")

    elif read_args.retriveArgs().renewal is False:
        filterusername = list(filter(lambda x: not x.renewed, filterusername))
        log.debug(f"disabled renewal filter username counta: {len(filterusername)}")
        trace_log_user(filterusername, "disabled renewal filter")

    log.debug(f"Sub status: {read_args.retriveArgs().sub_status}")
    if read_args.retriveArgs().sub_status:
        filterusername = list(filter(lambda x: x.active, filterusername))
        log.debug(f"active subscription filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "active subscription filter")

    elif read_args.retriveArgs().sub_status is False:
        filterusername = list(filter(lambda x: not x.active, filterusername))
        log.debug(f"expired subscription filter username count: {len(filterusername)}")
        trace_log_user(filterusername, "expired subscription filter")

    return filterusername
