import logging

import ofscraper.utils.args.globals as global_args


def subType(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Renewal: {global_args.getArgs().renewal}")
    if global_args.getArgs().renewal:
        filterusername = list(filter(lambda x: x.renewed, filterusername))
        log.debug(f"active renewal filter username count: {len(filterusername)}")
    elif global_args.getArgs().renewal is False:
        filterusername = list(filter(lambda x: not x.renewed, filterusername))
        log.debug(f"disabled renewal filter username counta: {len(filterusername)}")
    log.debug(f"Sub Status: {global_args.getArgs().sub_status}")
    if global_args.getArgs().sub_status:
        filterusername = list(filter(lambda x: x.active, filterusername))
        log.debug(f"active subscribtion filter username count: {len(filterusername)}")

    elif global_args.getArgs().sub_status is False:
        filterusername = list(filter(lambda x: not x.active, filterusername))
        log.debug(f"expired subscribtion filter username count: {len(filterusername)}")
    return filterusername
