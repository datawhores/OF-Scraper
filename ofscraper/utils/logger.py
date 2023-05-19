import logging
import re
import httpx
import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.theme import Theme
import ofscraper.utils.paths as paths
import ofscraper.utils.config as config_
import ofscraper.utils.args as args

senstiveDict={}

class DebugOnly(logging.Filter):
    def filter(self, record):
        if record.levelname=="DEBUG" or record.levelname=="TRACEBACK":
            return True
        return False
class NoDebug(logging.Filter):
    def filter(self, record):
        if record.levelname=="DEBUG" or record.levelname=="TRACEBACK":
            return False
        return True
class DiscordHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
    def emit(self, record):
        log_entry = self.format(record)
        url=config_.get_discord(config_.read_config())
        log_entry=f"{log_entry}\n\n"
        if url==None or url=="":
            return
        #convert markup
        log_entry=re.sub("\[bold\]|\[/bold\]","**",log_entry)
        httpx.post(url, headers={"Content-type": "application/json"},json={"content":log_entry})



class SensitiveFormatter(logging.Formatter):
    """Formatter that removes sensitive information in logs."""
    @staticmethod
    def _filter(s):
        s=re.sub("&Policy=[^&\"]+", "&Policy={hidden}", s)
        s=re.sub("&Signature=[^&\"]+", "&Signature={hidden}", s)
        s=re.sub("&Key-Pair-Id=[^&\"]+", "&Key-Pair-Id={hidden}", s)
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
    


def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(logging.DEBUG+5):
            self._log(logging.DEBUG+5, message, args, **kwargs)
def logToRoot(message, *args, **kwargs):
        logging.log(logging.DEBUG+5, message, *args, **kwargs)   

def addtrackback():

    logging.addLevelName(logging.DEBUG+5, "TRACEBACK")
    logging.TRACEBACK = logging.DEBUG+5
    setattr(logging.getLoggerClass(),"traceback", logForLevel)
    setattr(logging, "traceback",logToRoot)

def updateSenstiveDict(word,replacement):
     global senstiveDict
     senstiveDict[word]=replacement


def getLevel(input):
    """
    ERROR 50
    WARNING 30
    INFO 20
    DEBUG 10
    """
    return {"OFF":100,"PROMPT":"ERROR","LOW":"WARNING","NORMAL":"INFO","DEBUG":"DEBUG"}.get(input,100)

def init_logger(log):
    log.setLevel(1)
    addtrackback()
    # # #log file
      # #discord
    cord=DiscordHandler()
    cord.setLevel(getLevel(args.getargs().discord))
    cord.setFormatter(SensitiveFormatter('%(message)s'))
    console = Console(theme=Theme({"logging.level.error":"green","logging.level.warning": "green","logging.level.debug":"yellow","logging.level.info":"white","logging.level.traceback":"red"}))
    #console
    sh=RichHandler(rich_tracebacks=True, console=console,markup=True,tracebacks_show_locals=True,show_time=False,show_level=False)
    sh.setLevel(getLevel(args.getargs().output))
    sh.setFormatter(SensitiveFormatter('%(message)s'))
    sh.addFilter(NoDebug())
    log.addHandler(cord)
    log.addHandler(sh)
    if args.getargs().log!="OFF":
        stream=open(paths.getlogpath(), encoding='utf-8',mode="a",)
        fh=logging.StreamHandler(stream)
        fh.setLevel(getLevel(args.getargs().log))
        fh.setFormatter(LogFileFormatter('%(asctime)s - %(message)s',"%Y-%m-%d %H:%M:%S"))
        fh.addFilter(NoDebug())
        log.addHandler(fh)

    
    if args.getargs().output=="DEBUG":
        sh2=RichHandler(rich_tracebacks=True, console=console,markup=True,tracebacks_show_locals=True,show_time=False)
        sh2.setLevel(args.getargs().output)
        sh2.setFormatter(SensitiveFormatter('%(message)s'))
        sh2.addFilter(DebugOnly())
        log.addHandler(sh2)
    if args.getargs().log=="DEBUG":
        fh2=logging.StreamHandler(stream)
        fh2.setLevel(getLevel(args.getargs().log))
        fh2.setFormatter(LogFileFormatter('%(asctime)s - %(levelname)s - %(message)s',"%Y-%m-%d %H:%M:%S"))
        fh2.addFilter(DebugOnly())
        log.addHandler(fh2)
    return log


   

