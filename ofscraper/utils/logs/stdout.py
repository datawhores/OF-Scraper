# logs stdout logs via a shared queue

import logging
import queue
import threading
import traceback
from functools import partial
from logging.handlers import QueueHandler
from rich.logging import RichHandler
import zmq



import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.constants as constants
import ofscraper.utils.logs.classes.classes as log_class
from ofscraper.utils.logs.classes.handlers.zmq import ZMQHandler
from ofscraper.utils.logs.classes.handlers.rich import RichHandlerMulti

import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.helpers as log_helpers
def logger_process(input_, name=None, stop_count=1, event=None):
    # create a logger
    log = init_stdout_logger(name=name)
    input_ = input_ or log_globals.queue_
    count = 0
    funct = None
    if hasattr(input_, "get") and hasattr(input_, "put_nowait"):
        funct = partial(input_.get,timeout=constants.getattr("LOGGER_TIMEOUT"))
        end_funct = input_.get_nowait
    elif hasattr(input_, "send_pyobj"):
        funct = partial(input_.recv_pyobj, zmq.NOBLOCK)
    elif hasattr(input_, "send"):
        funct = input_.recv
    messages=[]
    while True:
        try:
            # consume a log message, block until one arrives
            if len(log.handlers) == 0:
                None
            if event and event.is_set():
                return
            message = funct()
            if not isinstance(message, list):
                messages.append(message)
            else:
                messages.extend(messages)
            if len(messages)>40:
                raise queue.Empty
        except (queue.Empty, zmq.ZMQError) as e:
            try:
                if len(messages)==0:
                    continue
                count = count + len([element for element in messages if (element is None or (hasattr(element, "message") and element.message == "None") or element == "None")])
                log_messages = [element for element in messages if hasattr(element, "message") and element.message != "None"]
                for  handler in log.handlers:
                    if isinstance(handler,RichHandlerMulti):    
                        handler.emit(*list(filter(lambda x:x.levelno >= handler.level,log_messages)))
                    else:
                        for message in log_messages:
                            if message.levelno >= handler.level:
                                handler.emit(message)
                if count == stop_count:
                    break
            except:
                continue
            finally:
                messages=[]
        except OSError as e:
            if str(e) == "handle is closed":
                print("handle is closed")
                return
            raise e
        except Exception as E:
            print(E)
            print(traceback.format_exc())
    while True:
        try:
            end_funct()
        except:
            break
    for handler in log.handlers:
        handler.close()
    log.handlers.clear()




# logger for print to console
def init_stdout_logger(name=None):
    log = logging.getLogger(name or "ofscraper_stdout")
    log=add_stdout_handler(log)
    return log


def init_rich_logger(name=None):
    log = logging.getLogger(name or "ofscraper_stdout_rich")
    log=add_rich_handler(log)
    return log


def add_rich_handler(log,clear=True):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
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
    log.addHandler(sh)
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
        log.addHandler(sh2)
    return log

def add_stdout_handler(log,clear=True):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
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
        mainhandle.name = "stdout"
    elif hasattr(main_, "send"):
        mainhandle =  QueueHandler(main_)
        mainhandle.name = "stdout"
    mainhandle.setLevel(log_helpers.getLevel(read_args.retriveArgs().output))
    # add a handler that uses the shared queue
    log.addHandler(mainhandle)
    return log

# process main queue logs to console must be ran by main process, sharable via queues
def start_stdout_logthread(input_=None, name=None, count=1, event=None):
    input = input_ or log_globals.queue_
    if input == log_globals.queue_:
        global main_log_thread
    main_log_thread = threading.Thread(
        target=logger_process,
        args=(input,),
        kwargs={"stop_count": count, "name": name, "event": event},
        daemon=True,
    )
    main_log_thread.start()
    return main_log_thread
