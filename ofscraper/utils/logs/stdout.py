#logs stdout logs via a shared queue

import logging
import queue
import threading
import traceback
from functools import partial
from logging.handlers import QueueHandler
from rich.logging import RichHandler



import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.logs.classes.classes as log_class
from ofscraper.utils.logs.classes.handlers.zmq import ZMQHandler
from ofscraper.utils.logs.classes.handlers.rich import RichHandlerMulti,flush_buffer
from ofscraper.utils.logs.classes.handlers.pipe import PipeHandler


import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.helpers as log_helpers
def logger_process(input_, name=None, stop_count=1, event=None,rich_thresholds=None):
    # create a logger
    log = init_stdout_logger(name=name,rich_thresholds=rich_thresholds)
    input_ = input_ or log_globals.queue_
    count = 0
    funct = None
    if hasattr(input_, "get") and hasattr(input_, "put_nowait"):
        funct = partial(input_.get,timeout=constants.getattr("LOGGER_TIMEOUT"))
    elif hasattr(input_, "send"):
        funct =  lambda: input_.recv() if input_.poll(constants.getattr("LOGGER_TIMEOUT")) else False
    while True:
        try:
            message = funct()
            if message=="None" or (hasattr(message, "message") and message.message=="None") or (hasattr(message, "message") and message.message==None):
                count=count+1
            elif message==False:
                pass
            else:
                log.handle(message)
        except (queue.Empty) as e:
           pass
        except OSError as e:
            if str(e) == "handle is closed":
                print("handle is closed")
                return
            raise e
        except Exception as E:
            print(E)
            print(traceback.format_exc())
        finally:
            if count == stop_count:
                # close_stdout_handlers()
                break
            if len(log.handlers) == 0:
                break
            if event and event.is_set():
                return
    for handler in log.handlers:
        handler.close()
    log.handlers.clear()



# logger for print to console
def init_stdout_logger(name=None,rich_thresholds=None):
    log = logging.getLogger(name or "ofscraper_stdout")
    log=add_stdout_handler(log,rich_thresholds=rich_thresholds)
    return log


def init_rich_logger(name=None):
    log = logging.getLogger(name or "ofscraper_stdout_rich")
    log=add_rich_handler(log)
    return log


def add_rich_handler(log,clear=True,rich_thresholds=None):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    rich_thresholds=rich_thresholds or {}
    sh =RichHandlerMulti(
        rich_tracebacks=False,
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_console(),
    )
    sh.buffer_size=rich_thresholds
    sh.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    sh.setFormatter(log_class.SensitiveFormatter(format))
    sh.addFilter(log_class.NoTraceBack())
    log.addHandler(sh)
    if read_args.retriveArgs().output in {"TRACE", "DEBUG"}:
        sh2 =  RichHandlerMulti(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )
        sh2.buffer_size=rich_thresholds

        sh2.setLevel(read_args.retriveArgs().output)
        sh2.setFormatter(log_class.SensitiveFormatter(format))
        sh2.addFilter(log_class.TraceBackOnly())
        log.addHandler(sh2)
    return log

def add_stdout_handler(log,clear=True,rich_thresholds=None):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    rich_thresholds=None or {}
    sh =RichHandlerMulti(
        rich_tracebacks=False,
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_console(),
    )
    sh.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    sh.setFormatter(log_class.SensitiveFormatter(format))
    sh.addFilter(log_class.NoTraceBack())
    sh.buffer_size=rich_thresholds
    tx = log_class.TextHandler()
    tx.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    tx.setFormatter(log_class.SensitiveFormatter(format))
    log.addHandler(sh)
    log.addHandler(tx)

    if read_args.retriveArgs().output in {"TRACE", "DEBUG"}:
        sh2 =  RichHandlerMulti(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )
        sh2.setLevel(read_args.retriveArgs().output)
        sh2.setFormatter(log_class.SensitiveFormatter(format))
        sh2.addFilter(log_class.TraceBackOnly())
        sh2.buffer_size=rich_thresholds

        log.addHandler(sh2)

    return log


def add_stdout_handler_multi(log,clear=True,main_=None):
    if clear:
        log.handlers.clear()
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    main_ = main_ or log_globals.queue_
    if hasattr(main_, "get") and hasattr(main_, "put_nowait"):
        mainhandle = QueueHandler(main_)
    elif hasattr(main_, "send"):        
        mainhandle =  PipeHandler(main_)
    mainhandle.name = "stdout"
    mainhandle.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    # add a handler that uses the shared queue
    log.addHandler(mainhandle)
    return log

# process main queue logs to console must be ran by main process, sharable via queues
def start_stdout_logthread(input_=None, name=None, count=1, event=None,rich_thresholds=None):
    input = input_ or log_globals.queue_d
    main_log_thread = threading.Thread(
        target=logger_process,
        args=(input,),
        kwargs={"stop_count": count, "name": name, "event": event,"rich_thresholds":rich_thresholds},
        daemon=True,
    )
    main_log_thread.start()
    log_globals.main_log_thread=main_log_thread
    return main_log_thread



def start_flush_thread(input_=None, name=None, count=1, event=None):
    flush_thread = threading.Thread(
        target=flush_buffer,
        kwargs={"event": event},
        daemon=True,
    )
    flush_thread.start()
    log_globals.flush_thread=flush_thread
    return flush_thread