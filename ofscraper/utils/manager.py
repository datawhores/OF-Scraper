manager=None
import multiprocess
def get_manager():
    global manager
    if manager==None:
        manager=multiprocess.Manager()
    return manager

def shutdown():
    if manager():
        manager.shutdown()


    