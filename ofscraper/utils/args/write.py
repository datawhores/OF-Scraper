import ofscraper.utils.args.globals as global_args
import ofscraper.utils.manager as manager


def setArgsV(changed):
    manager.get_manager_dict().update({"args": changed})
    setArgs(changed)


def setArgs(new_args):
    global_args.args = new_args
