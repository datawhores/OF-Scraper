import logging

import ofscraper.utils.args.globals as global_args

log = logging.getLogger("shared")



def setArgs(new_args):
    log.debug(f"args changing to {new_args}")
    global_args.args = new_args
