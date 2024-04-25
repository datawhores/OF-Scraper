import multiprocess

manager = None
manager_dict = None


def get_manager():
    global manager
    if manager:
        return manager
    manager = multiprocess.Manager()
    return manager


def get_manager_process_dict():
    global manager_dict
    manager = get_manager()
    if not manager_dict:
        manager_dict = manager.dict()
    return manager_dict


def shutdown():
    global manager
    if manager:
        manager.shutdown()
        manager is None


def update_dict(new_dict):
    manager_dict = get_manager_process_dict()
    manager_dict.update(new_dict)
    return manager_dict
