import logging
import re
import logging
import threading
import time
import queue
import types

from logging.handlers import QueueHandler
from rich.logging import RichHandler


from tenacity import retry,stop_after_attempt,retry_if_not_exception_type,wait_fixed
import aioprocessing
import ofscraper.utils.paths as paths
import ofscraper.utils.config as config_
import ofscraper.utils.args as args
import ofscraper.utils.console as console
import ofscraper.constants as constants
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.console as console_

queue_=aioprocessing.AioQueue()
otherqueue_=aioprocessing.AioQueue()

senstiveDict={}
process=""

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
    def emit(self, record):
        @retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_fixed(8))
        def inner(sess):
            with sess:
                with sess.requests(url,"post",headers={"Content-type": "application/json"},json={"content":log_entry})() as r:
                    if not r.status==204:
                        raise Exception

        log_entry = self.format(record)
        url=config_.get_discord(config_.read_config())
        log_entry=re.sub("\[bold\]|\[/bold\]","**",log_entry)
        log_entry=f"{log_entry}\n\n"
        if url==None or url=="":
            return
        inner(self.sess)
    


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
def getNumber(input_):
    input_=getLevel(input_)
    if isinstance(input_,str):return logging.getLevelName(input_)
    return input_

def init_main_logger(name=None):
    log=logging.getLogger(name or "ofscraper")
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

    if args.getargs().output in {"TRACE","DEBUG"}:
        funct=DebugOnly if args.getargs().output=="DEBUG" else TraceOnly
        sh2=RichHandler(rich_tracebacks=True, console=console.get_shared_console(),markup=True,tracebacks_show_locals=True,show_time=False)
        sh2.setLevel(args.getargs().output)
        sh2.setFormatter(SensitiveFormatter(format))
        sh2.addFilter(funct())
        log.addHandler(sh2)

    return log

def init_other_logger(name):
    name=name or "other"
    log=logging.getLogger(name)
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
    if args.getargs().log!="OFF":
        stream=open(paths.getlogpath(), encoding='utf-8',mode="a",)
        fh=logging.StreamHandler(stream)
        fh.setLevel(getLevel(args.getargs().log))
        fh.setFormatter(LogFileFormatter('%(asctime)s - %(message)s',"%Y-%m-%d %H:%M:%S"))
        fh.addFilter(NoDebug())
        log.addHandler(fh)
    if args.getargs().log in {"TRACE","DEBUG"}:
        funct=DebugOnly if args.getargs().output=="DEBUG" else TraceOnly
        fh2=logging.StreamHandler(stream)
        fh2.setLevel(getLevel(args.getargs().log))
        fh2.setFormatter(LogFileFormatter('%(asctime)s - %(levelname)s - %(message)s',"%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(funct())
        log.addHandler(fh2)
    return log

def add_widget(widget):
    [setattr(ele,"widget",widget) for ele in list(filter(lambda x:isinstance(x,TextHandler),logging.getLogger("ofscraper").handlers))]






#mulitprocess
# executed in a process that performs logging
def logger_process(input_,name=None,stop_count=1,event=None):
    # create a logger
    log=init_main_logger(name)
    input_=input_ or queue_
    count=0
    close=False
    while True:
        # consume a log message, block until one arrives
        if event and event.is_set():
            return
        messages = input_.get()
        if not isinstance(messages,list):
            messages=[messages]
        for message in messages:
            # check for shutdown
            if event and event.is_set():
                close=True
            #set close value
            if message=="None" :
                close=True
                continue    
            if message.message=="None":
                count=count+1
         
            if count==stop_count:
                close=True
            if message.message!="None":
                # log the message
                log.handle(message)
        # check close and empty message
        if close==True:
            return



#mulitprocess
# executed in a process that performs logging
def logger_other(input_,name=None,stop_count=1,event=None):
    # create a logger
    log=init_other_logger(name)
    count=0
    close=False
    if len(list(filter(lambda x:x.level!=100,log.handlers)))==0:
        return
    while True:
        # consume a log message, block until one arrives
        if event and event.is_set():
           return True
        messages = input_.get()
        if not isinstance(messages,list):
            messages=[messages]
        for message in messages:
            #set close value
            if event and event.is_set():
                close=True
            if message=="None":
                close=True
                continue    
            if message.message=="None":
                count=count+1
         
            if count==stop_count:
                close=True
            if message.message!="None":
                # log the message
                log.handle(message)
        # check close and empty message
        if close==True:
            return


# some inherantence from main process
def start_stdout_logthread(input_=None,name=None,count=1,event=None):
    input_=input_ or queue_
    thread= threading.Thread(target=logger_process,args=(input_,name,count,event),daemon=True)
    thread.start()


    return thread


def start_other_thread(input_=None,name=None,count=1,event=None):
    input_=input_ or otherqueue_
    thread= threading.Thread(target=logger_other,args=(input_,name,count,event),daemon=True)
    thread.start()
    return thread
    
def start_other_process(input_=None,name=None,count=1):
    def inner(input_=None,name=None,count=1):
        thread=start_other_thread(input_=None,name=None,count=1)
        thread.join()
        time.sleep(10)
    process=aioprocessing.AioProcess(target=inner,args=(input_,name,count)) if (args.getargs().log or args.getargs().discord) else None
    process.start() if process else None
    return process 

    



def get_shared_logger(main_=None ,other_=None,name=None):
    # create a logger
    logger = logging.getLogger(name or 'shared')
    addtraceback()
    addtrace()
    main_queue=QueueHandler(main_ or queue_)
    main_queue.setLevel(getLevel(args.getargs().output))
    # add a handler that uses the shared queue
    logger.addHandler(main_queue)
    discord_level=getNumber(args.getargs().discord); 
    file_level=getNumber(args.getargs().log); 
    other_queue=QueueHandler((other_ or otherqueue_))
    other_queue.setLevel(min(file_level,discord_level))
    logger.addHandler(other_queue)  
    # log all messages, debug and up
    logger.setLevel(1)
    return logger
    