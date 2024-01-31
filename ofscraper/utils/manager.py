manager = None
import multiprocess


def get_manager():
    global manager
    if manager:
        return manager
    manager = multiprocess.Manager()
    return manager


def shutdown():
    global manager
    if manager:
        manager.shutdown()

def update_dict(new_dict):
    manager=get_manager()
    curr_dict=manager.dict()
    curr_dict.update(new_dict)
    manager.dict(curr_dict)
