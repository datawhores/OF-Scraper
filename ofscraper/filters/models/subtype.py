import logging

import ofscraper.utils.args.read as read_args


def subType(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Renewal: {read_args.retriveArgs().renewal}")
    if read_args.retriveArgs().renewal:
        filterusername = list(filter(lambda x: x.renewed, filterusername))
        log.debug(f"active renewal filter username count: {len(filterusername)}")
    elif read_args.retriveArgs().renewal is False:
        filterusername = list(filter(lambda x: not x.renewed, filterusername))
        log.debug(f"disabled renewal filter username counta: {len(filterusername)}")
    log.debug(f"Sub Status: {read_args.retriveArgs().sub_status}")
    if read_args.retriveArgs().sub_status:
        filterusername = list(filter(lambda x: x.active, filterusername))
        log.debug(f"active subscribtion filter username count: {len(filterusername)}")

    elif read_args.retriveArgs().sub_status is False:
        filterusername = list(filter(lambda x: not x.active, filterusername))
        log.debug(f"expired subscribtion filter username count: {len(filterusername)}")
    return filterusername
