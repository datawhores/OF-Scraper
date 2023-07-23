import logging
import re
import logging
import threading
import time
import queue
from logging.handlers import QueueHandler
from rich.logging import RichHandler


from tenacity import retry,stop_after_attempt,wait_random
import aioprocessing
import ofscraper.utils.paths as paths
import ofscraper.utils.config as config_
import ofscraper.utils.args as args
import ofscraper.utils.console as console
import ofscraper.constants as constants
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.console as console_

queue_=aioprocessing.AioQueue()
queue2_=aioprocessing.AioQueue()

senstiveDict={}

class DebugOnly(logging.Filter):
    def filter(self, record):

        if record.levelno==10 or record.levelno==11:
            return True
        return False

class TraceOnly(logging.Filter):
    def filter(self, record):
        if record.levelno<=11:
            return True
        return False

class NoDebug(logging.Filter):
    def filter(self, record):
        if record.levelno<=11:
            return False
        return True
class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.sess=sessionbuilder.sessionBuilder(backend="httpx",set_header=False,set_cookies=False,set_sign=False)
    @retry(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX)) 
    def emit(self, record):
        log_entry = self.format(record)
        url=config_.get_discord(config_.read_config())
        log_entry=f"{log_entry}\n\n"
        if url==None or url=="":
            return
        with self.sess as sess:
            with sess.requests(url,"post",headers={"Content-type": "application/json"},json={"content":log_entry})() as r:
                None



class TextHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._widget=None
    def emit(self, record):
        # only emit after widget is set
        if self._widget==None:
            return
        log_entry = self.format(record)
        log_entry=f"{log_entry}"
        self._widget.write(log_entry)
        
    @property
    def widget(self):
        return self._widget
    @widget.setter
    def widget(self,widget):
        self._widget=widget

class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information in logs."""
    @staticmethod
    def _filter(s):
        if s.find("Avatar :")!=-1:
            None
        else:
            s=re.sub("&Policy=[^&\"\']+", "&Policy={hidden}", s)
            s=re.sub("&Signature=[^&\"\']+", "&Signature={hidden}", s)
            s=re.sub("&Key-Pair-Id=[^&\"\']+", "&Key-Pair-Id={hidden}", s)
            for ele in senstiveDict.items():
                s=re.sub(re.escape(str(ele[0])),str(ele[1]),s)
        return s

    def format(self, record):
        original = logging.Formatter.format(self, record)  # call parent method
        return self._filter(original)


class LogFileFormatter(SensitiveFormatter):
    """Formatter that removes sensitive information in logs."""

    @staticmethod
    def _filter(s):
        s=SensitiveFormatter._filter(s)
        s=re.sub("\[bold\]|\[/bold\]","",s)
        return s
    


def logForLevel(level):
    def inner(self, message, *args, **kwargs):
        if self.isEnabledFor(level):
            self._log(level, message, args, **kwargs)
    return inner

def  logToRoot(level):
    def inner(message, *args, **kwargs):
            logging.log(level, message, *args, **kwargs)  
    return inner 

def addtraceback():
    level=logging.DEBUG+1

    logging.addLevelName(level ,"TRACEBACK")
    logging.TRACEBACK = level
    setattr(logging, "TRACEBACK", level)
    setattr(logging.getLoggerClass(),"traceback", logForLevel(level))
    setattr(logging, "traceback",logToRoot(level))

def addtrace():
    level=logging.DEBUG-5

    logging.addLevelName( level,"TRACE")
    logging.TRACE = level
    setattr(logging, "TRACE", level)
    setattr(logging.getLoggerClass(),"trace", logForLevel(level))
    setattr(logging, "trace",logToRoot(level))



def updateSenstiveDict(word,replacement):
     global senstiveDict
     senstiveDict[word]=replacement


def getLevel(input):
    """
    CRITICAL 50
    ERROR 40
    WARNING 30
    INFO 20
    DEBUG 10
    TRACE 5 
    """
    return {"OFF":100,
            "PROMPT":"CRITICAL",
            "STATS":"ERROR",
            "LOW":"WARNING",
            "NORMAL":"INFO",
            "DEBUG":"DEBUG",
            "TRACE":"TRACE"
            
            }.get(input,100)

def init_main_logger():
    log=logging.getLogger("ofscraper")
    format=' \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s'
    log.setLevel(1)
    addtraceback()
    addtrace()
    # # #log file
      # #discord
    #console
    sh=RichHandler(rich_tracebacks=True,markup=True,tracebacks_show_locals=True,show_time=False,show_level=False,console=console.get_shared_console())
    sh.setLevel(getLevel(args.getargs().output))
    sh.setFormatter(SensitiveFormatter(format))
    sh.addFilter(NoDebug())
    tx=TextHandler()
    tx.setLevel(getLevel(args.getargs().output))
    tx.setFormatter(SensitiveFormatter(format))
    log.addHandler(sh)
    log.addHandler(tx)
    if args.getargs().log!="OFF":
        stream=open(paths.getlogpath(), encoding='utf-8',mode="a",)
        fh=logging.StreamHandler(stream)
        fh.setLevel(getLevel(args.getargs().log))
        fh.setFormatter(LogFileFormatter('%(asctime)s - %(message)s',"%Y-%m-%d %H:%M:%S"))
        fh.addFilter(NoDebug())
        log.addHandler(fh)

    
    if args.getargs().output in {"TRACE","DEBUG"}:
        funct=DebugOnly if args.getargs().output=="DEBUG" else TraceOnly
        sh2=RichHandler(rich_tracebacks=True, console=console.get_shared_console(),markup=True,tracebacks_show_locals=True,show_time=False)
        sh2.setLevel(args.getargs().output)
        sh2.setFormatter(SensitiveFormatter(format))
        sh2.addFilter(funct())
        log.addHandler(sh2)
    if args.getargs().log in {"TRACE","DEBUG"}:
        funct=DebugOnly if args.getargs().output=="DEBUG" else TraceOnly
        fh2=logging.StreamHandler(stream)
        fh2.setLevel(getLevel(args.getargs().log))
        fh2.setFormatter(LogFileFormatter('%(asctime)s - %(levelname)s - %(message)s',"%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(funct())
        log.addHandler(fh2)
    return log

def init_discord_logger():
    log=logging.getLogger("discord")
    format=' \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s'
    log.setLevel(1)
    addtraceback()
    addtrace()
    # # #log file
      # #discord
    cord=DiscordHandler()
    cord.setLevel(getLevel(args.getargs().discord))
    cord.setFormatter(SensitiveFormatter('%(message)s'))
    #console
    log.addHandler(cord)
    return log

def add_widget(widget):
    [setattr(ele,"widget",widget) for ele in list(filter(lambda x:isinstance(x,TextHandler),logging.getLogger("ofscraper").handlers))]



def logger_process_helper(console):
    console_.update_shared(console)
    logger_process()



#mulitprocess
# executed in a process that performs logging
def logger_process():
    # create a logger
    import time
    log=init_main_logger()
    while True:
        # consume a log message, block until one arrives
        message = queue_.get()
        # check for shutdown
        if message.message=="None":
            break
        # log the message
        log.handle(message)

#mulitprocess
# executed in a process that performs logging
def logger_discord():
    # create a logger
    log=init_discord_logger()
    if log.handlers[0].level==100:
        return
    while True:
        # consume a log message, block until one arrives
        message = queue2_.get()
        # check for shutdown
        if message.message=="None":
            break
        # log the message
        log.handle(message)       



# some inherantence from main process
def start_proc():
    threads=[threading.Thread(target=logger_process_helper,args=(console_.get_shared_console(),)),threading.Thread(target=logger_discord)]
    [thread.start() for thread in threads]

  
    



def get_shared_logger():
    # create a logger
    logger = logging.getLogger('shared')
    # add a handler that uses the shared queue
    logger.addHandler(QueueHandler(queue_))
    if args.getargs().discord:
        logger.addHandler(QueueHandler(queue2_))
    # log all messages, debug and up
    logger.setLevel(1)
    addtraceback()
    addtrace()
    # get the current process
    # report initial message
    return logger
    