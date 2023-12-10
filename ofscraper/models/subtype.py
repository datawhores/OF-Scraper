import logging

import ofscraper.utils.args as args_


def subType(filterusername):
    log = logging.getLogger("shared")
    log.debug(f"Renewal: {args_.getargs().renewal}")
    if args_.getargs().renewal == "active":
        filterusername = list(
            filter(lambda x: x.get("renewed") is not None, filterusername)
        )
        log.debug(f"active renewal filter username count: {len(filterusername)}")
    elif args_.getargs().renewal == "disabled":
        filterusername = list(
            filter(lambda x: x.get("renewed") is None, filterusername)
        )
        log.debug(f"disabled renewal filter username count: {len(filterusername)}")
    log.debug(f"Sub Status: {args_.getargs().sub_status}")
    if args_.getargs().sub_status == "active":
        filterusername = list(
            filter(lambda x: x.get("subscribed") is not None, filterusername)
        )
        log.debug(f"active subscribtion filter username count: {len(filterusername)}")

    elif args_.getargs().sub_status == "expired":
        filterusername = list(
            filter(lambda x: x.get("subscribed") is None, filterusername)
        )
        log.debug(f"expired subscribtion filter username count: {len(filterusername)}")
    return filterusername
