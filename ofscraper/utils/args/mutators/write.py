import logging

import ofscraper.utils.args.globals as global_args
import ofscraper.utils.manager as manager

log = logging.getLogger("shared")


def setArgsV(changed):
    log.debug(f"args changing to {changed}")
    manager.get_manager_process_dict().update({"args": changed})
    setArgs(changed)


def setArgs(new_args):
    log.debug(f"args changing to {new_args}")
    global_args.args = new_args
