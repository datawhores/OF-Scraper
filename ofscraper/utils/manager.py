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
