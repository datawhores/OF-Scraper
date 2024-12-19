import time
import logging


def start_threads(queue_threads, processes):
    [thread.start() for thread in queue_threads]
    [process.start() for process in processes]


def handle_threads(queue_threads, processes, log_threads):
    log = logging.getLogger("shared")
    log.debug(f"Initial Queue Threads: {queue_threads}")
    log.debug(f"Number of initial Queue Threads: {len(queue_threads)}")
    while True:
        newqueue_threads = list(filter(lambda x: x and x.is_alive(), queue_threads))
        if len(newqueue_threads) != len(queue_threads):
            log.debug(f"Remaining Queue Threads: {newqueue_threads}")
            log.debug(f"Number of Queue Threads: {len(newqueue_threads)}")
        if len(queue_threads) == 0:
            break
        queue_threads = newqueue_threads
        for thread in queue_threads:
            thread.join(timeout=0.1)
        time.sleep(0.5)
    log.debug(f"Intial Log Threads: {log_threads}")
    log.debug(f"Number of intial Log Threads: {len(log_threads)}")
    while True:
        new_logthreads = list(filter(lambda x: x and x.is_alive(), log_threads))
        if len(new_logthreads) != len(log_threads):
            log.debug(f"Remaining Log Threads: {new_logthreads}")
            log.debug(f"Number of Log Threads: {len(new_logthreads)}")
        if len(new_logthreads) == 0:
            break
        log_threads = new_logthreads
        for thread in log_threads:
            thread.join(timeout=0.1)
        time.sleep(0.5)
    log.debug(f"Initial download threads: {processes}")
    log.debug(f"Initial Number of download threads: {len(processes)}")
    while True:
        new_proceess = list(filter(lambda x: x and x.is_alive(), processes))
        if len(new_proceess) != len(processes):
            log.debug(f"Remaining Processes: {new_proceess}")
            log.debug(f"Number of Processes: {len(new_proceess)}")
        if len(new_proceess) == 0:
            break
        processes = new_proceess
        for process in processes:
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
        time.sleep(0.5)
